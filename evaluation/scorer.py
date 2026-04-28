"""Scoring utilities for conversation evaluation."""

from __future__ import annotations

import argparse
import csv
import math
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Tuple

from .utils import ARTIFACTS_DIR, ensure_dirs, load_json, token_set, write_json


STOPWORDS = {
    "the", "a", "an", "and", "or", "to", "of", "for", "in", "on", "is", "are", "was", "were",
    "be", "been", "being", "it", "that", "this", "with", "as", "by", "at", "from", "if", "then",
    "than", "also", "about", "into", "we", "you", "they", "i", "he", "she", "them", "our", "their",
}
ABSTAIN_PATTERNS = [
    "not enough", "insufficient", "cannot find", "not in the corpus", "not available", "outside the corpus",
    "no evidence", "i cannot", "i don't have", "unable to verify",
]


def _import_metrics():
    from nltk.translate.bleu_score import SmoothingFunction, sentence_bleu
    from rouge_score import rouge_scorer
    from bert_score import score as bertscore_score

    return sentence_bleu, SmoothingFunction, rouge_scorer, bertscore_score


def _content_tokens(text: str) -> List[str]:
    toks = re.findall(r"\b[a-zA-Z][a-zA-Z0-9+\-]{2,}\b", (text or "").lower())
    return [t for t in toks if t not in STOPWORDS]


def _split_sentences(text: str) -> List[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text or "") if s.strip()]


def faithfulness_heuristic(answer: str, contexts: List[Dict[str, Any]], expected_in_corpus: bool) -> Tuple[int, Dict[str, float | int | bool]]:
    answer = answer or ""
    context_text = " ".join((c.get("title", "") + " " + c.get("body", "")) for c in (contexts or []))

    ans_tokens = _content_tokens(answer)
    ctx_tokens = set(_content_tokens(context_text))
    if not ans_tokens:
        return 0, {"support_ratio": 0.0, "unsupported_sentence_ratio": 1.0, "abstained": False}

    overlap = sum(1 for t in ans_tokens if t in ctx_tokens)
    support_ratio = overlap / max(1, len(ans_tokens))

    ctx_sents = _split_sentences(context_text)
    ans_sents = _split_sentences(answer)

    unsupported = 0
    factual_sents = 0
    for sent in ans_sents:
        stoks = [t for t in _content_tokens(sent) if len(t) > 3]
        if len(stoks) < 5:
            continue
        factual_sents += 1
        sset = set(stoks)
        best = 0.0
        for c in ctx_sents[:80]:
            cset = set(_content_tokens(c))
            if not cset:
                continue
            j = len(sset & cset) / len(sset | cset)
            if j > best:
                best = j
        if best < 0.18:
            unsupported += 1

    unsupported_ratio = unsupported / factual_sents if factual_sents else 0.0
    abstained = any(p in answer.lower() for p in ABSTAIN_PATTERNS)

    if expected_in_corpus:
        faithful = int(support_ratio >= 0.55 and unsupported_ratio <= 0.40)
    else:
        faithful = int(abstained or support_ratio < 0.35)

    return faithful, {
        "support_ratio": round(support_ratio, 4),
        "unsupported_sentence_ratio": round(unsupported_ratio, 4),
        "abstained": bool(abstained),
        "num_factual_sentences": int(factual_sents),
    }


def score_records(raw_payload: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    sentence_bleu, SmoothingFunction, rouge_scorer, bertscore_score = _import_metrics()

    records = raw_payload["records"]
    good = [r for r in records if r.get("answer") and not r.get("error")]

    cands = [r["answer"] for r in good]
    refs = [r["reference_answer"] for r in good]

    # Batch BERTScore for reproducibility and speed.
    # Use a lighter checkpoint to keep runtime practical on local machines.
    _, _, bert_f1 = bertscore_score(cands, refs, lang="en", model_type="distilbert-base-uncased", verbose=False)

    rs = rouge_scorer.RougeScorer(["rougeL"], use_stemmer=True)
    smooth = SmoothingFunction().method3

    bert_idx = 0
    per_sample: List[Dict[str, Any]] = []

    for r in records:
        row = {
            "question_id": r["question_id"],
            "question_type": r["question_type"],
            "provider": r["provider"],
            "model": r["model"],
            "expected_in_corpus": bool(r["expected_in_corpus"]),
            "error": r.get("error"),
        }

        if r.get("answer") and not r.get("error"):
            ref = r["reference_answer"]
            hyp = r["answer"]
            bleu = sentence_bleu([ref.split()], hyp.split(), smoothing_function=smooth)
            rouge_l = rs.score(ref, hyp)["rougeL"].fmeasure
            bert = float(bert_f1[bert_idx].item())
            bert_idx += 1
            faithful, details = faithfulness_heuristic(hyp, r.get("contexts", []), bool(r["expected_in_corpus"]))

            row.update(
                {
                    "bleu": round(float(bleu), 4),
                    "rougeL": round(float(rouge_l), 4),
                    "bertscore_f1": round(float(bert), 4),
                    "faithful": faithful,
                    "support_ratio": details["support_ratio"],
                    "unsupported_sentence_ratio": details["unsupported_sentence_ratio"],
                    "abstained": details["abstained"],
                    "answer_chars": len(hyp),
                }
            )
        else:
            row.update(
                {
                    "bleu": math.nan,
                    "rougeL": math.nan,
                    "bertscore_f1": math.nan,
                    "faithful": 0,
                    "support_ratio": 0.0,
                    "unsupported_sentence_ratio": 1.0,
                    "abstained": False,
                    "answer_chars": 0,
                }
            )

        per_sample.append(row)

    grouped: Dict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
    for row in per_sample:
        grouped[(row["provider"], row["model"])].append(row)

    aggregates: List[Dict[str, Any]] = []
    for (provider, model), rows in grouped.items():
        valid = [r for r in rows if not r.get("error")]
        n = len(rows)
        n_valid = len(valid)

        def avg(field: str) -> float:
            if not valid:
                return float("nan")
            vals = [float(r[field]) for r in valid]
            return round(sum(vals) / len(vals), 4)

        faithfulness_pct = round((sum(r["faithful"] for r in rows) / max(1, n)) * 100.0, 2)
        adversarial = [r for r in rows if not r["expected_in_corpus"]]
        adv_refusal_pct = round((sum(1 for r in adversarial if r["abstained"]) / max(1, len(adversarial))) * 100.0, 2)

        aggregates.append(
            {
                "provider": provider,
                "model": model,
                "num_questions": n,
                "num_success": n_valid,
                "num_failed": n - n_valid,
                "bleu": avg("bleu"),
                "rougeL": avg("rougeL"),
                "bertscore_f1": avg("bertscore_f1"),
                "faithfulness_pct": faithfulness_pct,
                "avg_support_ratio": avg("support_ratio"),
                "adversarial_refusal_pct": adv_refusal_pct,
            }
        )

    return per_sample, aggregates


def _write_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    if not rows:
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Score conversation model outputs")
    parser.add_argument("--input", default="raw_model_outputs.json")
    parser.add_argument("--per-sample-json", default="per_sample_scores.json")
    parser.add_argument("--per-sample-csv", default="per_sample_scores.csv")
    parser.add_argument("--aggregate-json", default="aggregate_metrics.json")
    parser.add_argument("--aggregate-csv", default="aggregate_metrics.csv")
    args = parser.parse_args()

    ensure_dirs()
    payload = load_json(ARTIFACTS_DIR / args.input)
    per_sample, aggregates = score_records(payload)

    write_json(ARTIFACTS_DIR / args.per_sample_json, {"rows": per_sample})
    write_json(ARTIFACTS_DIR / args.aggregate_json, {"rows": aggregates})
    _write_csv(ARTIFACTS_DIR / args.per_sample_csv, per_sample)
    _write_csv(ARTIFACTS_DIR / args.aggregate_csv, aggregates)
    print(f"Scoring complete: {ARTIFACTS_DIR / args.aggregate_csv}")


if __name__ == "__main__":
    main()
