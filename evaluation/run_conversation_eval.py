"""One-command entrypoint for full conversation system evaluation."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from evaluation.dataset_builder import DATASET_PATH, build_dataset
from evaluation.report_generator import generate_report
from evaluation.runner import run_eval
from evaluation.scorer import score_records
from evaluation.utils import ARTIFACTS_DIR, DATA_DIR, REPORTS_DIR, ensure_dirs, write_json


def main() -> None:
    parser = argparse.ArgumentParser(description="Run full conversation system evaluation pipeline")
    parser.add_argument("--top-k", type=int, default=8)
    parser.add_argument("--providers", default="groq,google")
    args = parser.parse_args()

    ensure_dirs()

    dataset = build_dataset(top_k=args.top_k)
    write_json(DATA_DIR / "conversation_eval_questions.json", dataset)

    providers = [p.strip() for p in args.providers.split(",") if p.strip()]
    raw = run_eval(dataset_path="conversation_eval_questions.json", top_k=args.top_k, providers=providers)
    write_json(ARTIFACTS_DIR / "raw_model_outputs.json", raw)

    per_sample, aggregate = score_records(raw)
    write_json(ARTIFACTS_DIR / "per_sample_scores.json", {"rows": per_sample})
    write_json(ARTIFACTS_DIR / "aggregate_metrics.json", {"rows": aggregate})

    # Write CSVs using scorer CLI for consistency.
    subprocess.run([sys.executable, "-m", "evaluation.scorer"], check=True)

    report = generate_report(
        dataset_path="conversation_eval_questions.json",
        raw_path="raw_model_outputs.json",
        aggregate_path="aggregate_metrics.json",
        per_sample_path="per_sample_scores.json",
        output_name="conversation_system_evaluation_report.docx",
    )

    print("Evaluation complete.")
    print(f"Dataset: {DATASET_PATH}")
    print(f"Raw outputs: {ARTIFACTS_DIR / 'raw_model_outputs.json'}")
    print(f"Per-sample scores: {ARTIFACTS_DIR / 'per_sample_scores.csv'}")
    print(f"Aggregate metrics: {ARTIFACTS_DIR / 'aggregate_metrics.csv'}")
    print(f"Report: {report}")


if __name__ == "__main__":
    main()
