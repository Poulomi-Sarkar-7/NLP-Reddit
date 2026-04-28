import re
import numpy as np
import pandas as pd
from sacrebleu.metrics import CHRF, BLEU
from rouge_score import rouge_scorer

try:
    from bert_score import score as bertscore_score
except Exception:
    bertscore_score = None


def _safe_text(x):
    if x is None:
        return ""
    if isinstance(x, float) and np.isnan(x):
        return ""
    return str(x).strip()


def compute_reference_metrics(df: pd.DataFrame, pred_col: str, ref_col: str = "ground_truth_bengali") -> pd.DataFrame:
    refs = [_safe_text(v) for v in df[ref_col].tolist()]
    preds = [_safe_text(v) for v in df[pred_col].tolist()]

    chrf = CHRF(word_order=2)
    bleu = BLEU(effective_order=True)
    rouge = rouge_scorer.RougeScorer(["rouge1", "rouge2", "rougeL"], use_stemmer=False)

    rows = []
    for idx, (r, p) in enumerate(zip(refs, preds)):
        chr_f = chrf.sentence_score(p, [r]).score
        bleu_s = bleu.sentence_score(p, [r]).score
        rg = rouge.score(r, p)
        rows.append(
            {
                "index": idx,
                "system": pred_col,
                "chrf": chr_f,
                "bleu": bleu_s,
                "rouge1_f": rg["rouge1"].fmeasure,
                "rouge2_f": rg["rouge2"].fmeasure,
                "rougeL_f": rg["rougeL"].fmeasure,
            }
        )

    per_row = pd.DataFrame(rows)

    if bertscore_score is not None:
        try:
            _, _, f1 = bertscore_score(
                cands=preds,
                refs=refs,
                model_type="xlm-roberta-base",
                lang="bn",
                verbose=False,
                rescale_with_baseline=False,
            )
            per_row["bertscore_f1"] = [float(v) for v in f1]
        except Exception:
            per_row["bertscore_f1"] = np.nan
    else:
        per_row["bertscore_f1"] = np.nan

    return per_row


def aggregate_metrics(per_row: pd.DataFrame) -> pd.DataFrame:
    metric_cols = ["chrf", "bleu", "rouge1_f", "rouge2_f", "rougeL_f", "bertscore_f1"]
    out = []
    for system, g in per_row.groupby("system"):
        row = {"system": system, "count": int(len(g))}
        for c in metric_cols:
            vals = g[c].dropna()
            row[f"{c}_mean"] = float(vals.mean()) if len(vals) else np.nan
            row[f"{c}_median"] = float(vals.median()) if len(vals) else np.nan
            row[f"{c}_std"] = float(vals.std(ddof=0)) if len(vals) else np.nan
        out.append(row)
    return pd.DataFrame(out)


def score_to_likert(score: float, thresholds=(0.20, 0.35, 0.50, 0.65)) -> int:
    t1, t2, t3, t4 = thresholds
    if score < t1:
        return 1
    if score < t2:
        return 2
    if score < t3:
        return 3
    if score < t4:
        return 4
    return 5


def build_manual_eval_sheet(df: pd.DataFrame, per_row: pd.DataFrame, system_col: str, sample_n: int = 8, seed: int = 42) -> pd.DataFrame:
    sample_n = max(5, min(10, sample_n))
    g = per_row[per_row["system"] == system_col].copy()
    if len(g) == 0:
        return pd.DataFrame()
    take = min(sample_n, len(g))
    sampled = g.sample(n=take, random_state=seed).sort_values("index")

    rows = []
    for _, r in sampled.iterrows():
        idx = int(r["index"])
        flu = score_to_likert(float(r["rougeL_f"]))
        adeq = score_to_likert(float(r["chrf"]) / 100.0)
        rows.append(
            {
                "row_id": df.iloc[idx].get("row_id", idx + 1),
                "source_text": _safe_text(df.iloc[idx]["source_text"]),
                "ground_truth_bengali": _safe_text(df.iloc[idx]["ground_truth_bengali"]),
                "system": system_col,
                "system_translation": _safe_text(df.iloc[idx][system_col]),
                "fluency_1to5": flu,
                "adequacy_1to5": adeq,
            }
        )
    return pd.DataFrame(rows)


def markdown_table(df: pd.DataFrame) -> str:
    if df.empty:
        return "_No data_"
    return df.to_markdown(index=False)


def sanitize_for_report(txt: str) -> str:
    txt = re.sub(r"\s+", " ", str(txt)).strip()
    return txt[:220] + ("..." if len(txt) > 220 else "")
