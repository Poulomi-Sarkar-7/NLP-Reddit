from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from rag_service import available_providers, generate_answer, retrieve_context

from bias_eval.report import write_bias_report
from bias_eval.scoring import category_summary, global_findings, score_probe_result

PROBES_PATH = ROOT / "probes.json"
ARTIFACTS_ROOT = ROOT / "artifacts"
DEFAULT_MODELS = {
    "groq": "llama-3.3-70b-versatile",
    "google": "gemini-2.5-flash",
}


def load_probes(path: Path) -> List[Dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def pick_provider(requested: str) -> str:
    flags = available_providers()
    if requested in ("groq", "google") and flags.get(requested):
        return requested
    for p in ("groq", "google"):
        if flags.get(p):
            return p
    return "none"


def safe_generate(question: str, contexts: List[Dict], provider: str, model: str, retries: int = 2) -> Dict:
    if provider == "none":
        return {"answer": None, "error": "No available provider key found (GROQ_API_KEY / GOOGLE_API_KEY)."}

    err = None
    for attempt in range(retries + 1):
        try:
            ans = generate_answer(question, contexts, provider=provider, model=model)
            return {"answer": ans, "error": None}
        except Exception as ex:
            err = str(ex)
            if attempt < retries:
                time.sleep(1.5 * (attempt + 1))
    return {"answer": None, "error": err}


def write_csv(path: Path, rows: List[Dict], columns: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        for r in rows:
            writer.writerow({c: r.get(c, "") for c in columns})


def run(top_k: int = 8, provider: str = "auto") -> Path:
    probes = load_probes(PROBES_PATH)
    chosen_provider = pick_provider(provider if provider != "auto" else "")
    chosen_model = DEFAULT_MODELS.get(chosen_provider)

    run_ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    run_dir = ARTIFACTS_ROOT / run_ts
    run_dir.mkdir(parents=True, exist_ok=True)

    raw_rows = []
    scored_rows = []

    for p in probes:
        contexts = retrieve_context(p["question"], top_k=top_k)
        gen = safe_generate(
            question=p["question"],
            contexts=contexts,
            provider=chosen_provider,
            model=chosen_model,
            retries=2,
        )

        row = {
            "probe_id": p["probe_id"],
            "category": p["category"],
            "question": p["question"],
            "expected_risk_type": p["expected_risk_type"],
            "provider": chosen_provider,
            "model": chosen_model,
            "top_k": top_k,
            "contexts": contexts,
            "answer": gen["answer"],
            "error": gen["error"],
        }
        raw_rows.append(row)

        scored = score_probe_result(row)
        scored_rows.append(scored)

    metadata = {
        "run_timestamp": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "provider": chosen_provider,
        "model": chosen_model,
        "top_k": top_k,
        "probe_count": len(probes),
        "provider_flags": available_providers(),
    }

    raw_path = run_dir / "raw_outputs.json"
    raw_payload = {"metadata": metadata, "rows": raw_rows}
    raw_path.write_text(json.dumps(raw_payload, indent=2, ensure_ascii=False), encoding="utf-8")

    scored_path = run_dir / "scored_results.csv"
    scored_columns = [
        "probe_id", "category", "expected_risk_type", "provider", "model", "error",
        "corpus_bias_present", "corpus_harmful_generalization_score", "stereotype_present",
        "harmful_generalization_score", "uncertainty_calibration", "smudging_flag", "label_rationale"
    ]
    write_csv(scored_path, scored_rows, scored_columns)

    cat_rows = category_summary(scored_rows)
    cat_path = run_dir / "category_summary.csv"
    cat_cols = [
        "category", "n", "corpus_bias_rate", "model_stereotype_rate",
        "smudging_rate", "avg_harmful_generalization", "uncertainty_good_rate"
    ]
    write_csv(cat_path, cat_rows, cat_cols)

    global_stats = global_findings(scored_rows)
    report_path = run_dir / "bias_detection_report.md"
    write_bias_report(report_path, metadata, scored_rows, cat_rows, global_stats)

    print(f"Bias evaluation complete. Artifacts: {run_dir}")
    print(f"- Raw outputs: {raw_path}")
    print(f"- Scored results: {scored_path}")
    print(f"- Category summary: {cat_path}")
    print(f"- Report: {report_path}")

    return run_dir


def main() -> None:
    parser = argparse.ArgumentParser(description="Run bias detection evaluation for Reddit RAG")
    parser.add_argument("--top-k", type=int, default=8)
    parser.add_argument("--provider", default="auto", choices=["auto", "groq", "google"])
    args = parser.parse_args()

    run(top_k=args.top_k, provider=args.provider)


if __name__ == "__main__":
    main()
