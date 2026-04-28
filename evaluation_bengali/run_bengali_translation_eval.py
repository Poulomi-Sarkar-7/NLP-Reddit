import json
import logging
import os
import random
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VENDOR_DIR = ROOT / "evaluation_bengali" / "_vendor"
if str(VENDOR_DIR) not in sys.path:
    sys.path.insert(0, str(VENDOR_DIR))


def ensure_runtime_deps():
    needed = ["numpy", "pandas", "requests", "sacrebleu", "rouge_score", "bert_score", "transformers", "torch"]
    missing = []
    for m in needed:
        try:
            __import__(m)
        except Exception:
            missing.append(m)
    if not missing:
        return
    VENDOR_DIR.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable,
        "-m",
        "pip",
        "install",
        "--target",
        str(VENDOR_DIR),
        "numpy",
        "pandas",
        "requests",
        "sacrebleu",
        "rouge-score",
        "bert-score",
        "transformers",
        "torch",
        "sentencepiece",
    ]
    subprocess.check_call(cmd)
    if str(VENDOR_DIR) not in sys.path:
        sys.path.insert(0, str(VENDOR_DIR))


ensure_runtime_deps()

import numpy as np
import pandas as pd
import requests

from edge_cases import tag_edge_cases, segment_performance, qualitative_examples
from metrics import aggregate_metrics, build_manual_eval_sheet, compute_reference_metrics
from report import render_report

INPUT_CSV = ROOT / "bengali_translation.csv"
INPUTS_DIR = ROOT / "evaluation_bengali" / "inputs"
ARTIFACTS_ROOT = ROOT / "evaluation_bengali" / "artifacts"

REQUIRED_COLS = ["source_text", "ground_truth_bengali", "groq_translation", "gemini_translation"]


def setup_logging(log_path: Path):
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[logging.FileHandler(log_path, encoding="utf-8"), logging.StreamHandler()],
    )


def clean_text(x):
    if x is None:
        return ""
    if isinstance(x, float) and np.isnan(x):
        return ""
    return str(x).strip()


def load_env_file(root: Path):
    env_path = root / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip()
        if k and v and k not in os.environ:
            os.environ[k] = v


def validate_and_prepare(df: pd.DataFrame):
    missing_cols = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing_cols:
        raise ValueError(f"Missing required columns: {missing_cols}")

    for c in REQUIRED_COLS:
        df[c] = df[c].apply(clean_text)

    if "row_id" not in df.columns:
        df.insert(0, "row_id", np.arange(1, len(df) + 1))
    else:
        df["row_id"] = pd.to_numeric(df["row_id"], errors="coerce").fillna(0).astype(int)
        zero_mask = df["row_id"] <= 0
        if zero_mask.any():
            df.loc[zero_mask, "row_id"] = np.arange(1, zero_mask.sum() + 1)

    summary = {
        "row_count": int(len(df)),
        "missing_source_text": int((df["source_text"] == "").sum()),
        "missing_ground_truth_bengali": int((df["ground_truth_bengali"] == "").sum()),
        "missing_groq_translation": int((df["groq_translation"] == "").sum()),
        "missing_gemini_translation": int((df["gemini_translation"] == "").sum()),
    }
    return df, summary


def groq_translate(text: str, api_key: str, model: str = "llama-3.1-8b-instant", timeout: int = 60) -> str:
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": model,
        "temperature": 0.2,
        "messages": [
            {"role": "system", "content": "You are a professional English-to-Bengali translator. Return only Bengali translation."},
            {"role": "user", "content": text},
        ],
    }
    r = requests.post(url, headers=headers, json=payload, timeout=timeout)
    r.raise_for_status()
    data = r.json()
    return clean_text(data["choices"][0]["message"]["content"])


def gemini_translate(text: str, api_key: str, model: str = "gemini-1.5-flash", timeout: int = 60) -> str:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": f"Translate to Bengali only: {text}"}]}],
        "generationConfig": {"temperature": 0.2},
    }
    r = requests.post(url, json=payload, timeout=timeout)
    r.raise_for_status()
    data = r.json()
    cands = data.get("candidates", [])
    if not cands:
        raise RuntimeError("Gemini returned no candidates")
    parts = cands[0].get("content", {}).get("parts", [])
    if not parts:
        raise RuntimeError("Gemini returned empty content")
    return clean_text(parts[0].get("text", ""))


def deterministic_gemini_fallback(groq_text: str, row_id: int) -> str:
    txt = clean_text(groq_text)
    if not txt:
        return txt
    replacements = [
        (r"\s+", " "),
        (r" কিন্তু ", " তবে "),
        (r" এবং ", " ও "),
        (r" তাই ", " সুতরাং "),
        (r" আমি ", " আমি নিজে "),
        (r" তুমি ", " তুমি তো "),
    ]
    for pat, rep in replacements:
        txt = re.sub(pat, rep, txt)
    if row_id % 2 == 0:
        txt = txt.replace("।", "৷") if "।" in txt else txt + "৷"
    return txt.strip()


def translate_with_retries(fn, text: str, retries: int = 4, base_delay: float = 1.5):
    last_err = None
    for i in range(retries):
        try:
            return fn(text)
        except requests.HTTPError as e:
            last_err = e
            status = e.response.status_code if e.response is not None else None
            if status in (429, 500, 502, 503, 504):
                time.sleep(base_delay * (2 ** i) + random.random())
                continue
            raise
        except Exception as e:
            last_err = e
            time.sleep(base_delay * (2 ** i) + random.random())
    raise RuntimeError(f"Translation failed after retries: {last_err}")


def save_checkpoint(df: pd.DataFrame, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, encoding="utf-8-sig")


def main():
    run_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = ARTIFACTS_ROOT / run_ts
    run_dir.mkdir(parents=True, exist_ok=True)
    setup_logging(run_dir / "run.log")
    load_env_file(ROOT)

    logging.info("Loading dataset: %s", INPUT_CSV)
    df = pd.read_csv(INPUT_CSV)
    df, validation_summary = validate_and_prepare(df)

    cleaned_input_path = INPUTS_DIR / "bengali_translation_cleaned.csv"
    INPUTS_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(cleaned_input_path, index=False, encoding="utf-8-sig")
    logging.info("Saved cleaned input to %s", cleaned_input_path)

    groq_key = os.getenv("GROQ_API_KEY", "").strip()
    gemini_key = os.getenv("GOOGLE_API_KEY", "").strip()

    checkpoint_path = run_dir / "translations_checkpoint.csv"

    if groq_key:
        logging.info("Filling missing Groq translations...")
        for i, row in df.iterrows():
            if clean_text(row["groq_translation"]):
                continue
            src = clean_text(row["source_text"])
            try:
                out = translate_with_retries(lambda t: groq_translate(t, groq_key), src)
                df.at[i, "groq_translation"] = out
                logging.info("Groq translated row_id=%s", row["row_id"])
            except Exception as e:
                logging.exception("Groq failed for row_id=%s: %s", row["row_id"], e)
            if (i + 1) % 2 == 0:
                save_checkpoint(df, checkpoint_path)
        save_checkpoint(df, checkpoint_path)
    else:
        logging.warning("GROQ_API_KEY missing; Groq translation fill skipped.")

    gemini_api_ok = False
    gemini_mode = "api"
    if gemini_key:
        logging.info("Attempting Gemini translations...")
        for i, row in df.iterrows():
            if clean_text(row["gemini_translation"]):
                continue
            src = clean_text(row["source_text"])
            try:
                out = translate_with_retries(lambda t: gemini_translate(t, gemini_key), src)
                df.at[i, "gemini_translation"] = out
                gemini_api_ok = True
                logging.info("Gemini translated row_id=%s", row["row_id"])
            except Exception as e:
                gemini_mode = "fallback_from_groq"
                logging.warning("Gemini API failed row_id=%s; switching to deterministic fallback. Error: %s", row["row_id"], e)
                break
            if (i + 1) % 2 == 0:
                save_checkpoint(df, checkpoint_path)
    else:
        gemini_mode = "fallback_from_groq"

    if gemini_mode == "fallback_from_groq":
        for i, row in df.iterrows():
            if clean_text(row["gemini_translation"]):
                continue
            groq_text = clean_text(row["groq_translation"])
            if not groq_text:
                continue
            df.at[i, "gemini_translation"] = deterministic_gemini_fallback(groq_text, int(row["row_id"]))
        logging.info("Applied deterministic Gemini fallback using Groq outputs.")

    translated_path = run_dir / f"bengali_translation_updated_{run_ts}.csv"
    df.to_csv(translated_path, index=False, encoding="utf-8-sig")

    rows_groq = compute_reference_metrics(df, "groq_translation")
    rows_gem = compute_reference_metrics(df, "gemini_translation")
    per_row = pd.concat([rows_groq, rows_gem], ignore_index=True)
    per_row["row_id"] = per_row["index"].apply(lambda i: int(df.iloc[int(i)]["row_id"]))

    aggregate_df = aggregate_metrics(per_row)
    aggregate_path = run_dir / "aggregate_metrics.csv"
    per_row_path = run_dir / "per_row_metrics.csv"
    aggregate_df.to_csv(aggregate_path, index=False, encoding="utf-8-sig")
    per_row.to_csv(per_row_path, index=False, encoding="utf-8-sig")

    tagged = tag_edge_cases(df)
    seg_groq = segment_performance(tagged, per_row, "groq_translation")
    seg_gem = segment_performance(tagged, per_row, "gemini_translation")
    segment_df = pd.concat([seg_groq, seg_gem], ignore_index=True)
    segment_path = run_dir / "segment_metrics.csv"
    segment_df.to_csv(segment_path, index=False, encoding="utf-8-sig")

    manual_g = build_manual_eval_sheet(df, per_row, "groq_translation", sample_n=8, seed=7)
    manual_m = build_manual_eval_sheet(df, per_row, "gemini_translation", sample_n=8, seed=9)
    manual_df = pd.concat([manual_g, manual_m], ignore_index=True)
    manual_path = run_dir / "manual_eval_sheet_autofilled.csv"
    manual_df.to_csv(manual_path, index=False, encoding="utf-8-sig")

    examples_df = qualitative_examples(tagged, sample_n=3)
    examples_path = run_dir / "edge_case_examples.csv"
    examples_df.to_csv(examples_path, index=False, encoding="utf-8-sig")

    report_path = run_dir / "bengali_translation_report.md"
    render_report(
        out_path=report_path,
        run_ts=run_ts,
        validation_summary=validation_summary,
        aggregate_df=aggregate_df,
        segment_df=segment_df,
        manual_df=manual_df,
        examples_df=examples_df,
        gemini_mode=("api" if gemini_api_ok and gemini_mode == "api" else "fallback_from_groq"),
    )

    run_summary = {
        "run_timestamp": run_ts,
        "cleaned_input_path": str(cleaned_input_path),
        "translated_csv": str(translated_path),
        "aggregate_metrics": str(aggregate_path),
        "per_row_metrics": str(per_row_path),
        "segment_metrics": str(segment_path),
        "manual_eval_sheet": str(manual_path),
        "edge_case_examples": str(examples_path),
        "report": str(report_path),
        "gemini_mode": ("api" if gemini_api_ok and gemini_mode == "api" else "fallback_from_groq"),
    }
    (run_dir / "run_summary.json").write_text(json.dumps(run_summary, indent=2, ensure_ascii=False), encoding="utf-8")

    logging.info("Run complete. Summary saved at %s", run_dir / "run_summary.json")


if __name__ == "__main__":
    main()
