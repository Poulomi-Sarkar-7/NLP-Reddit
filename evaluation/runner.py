"""Run model answers for conversation evaluation questions across providers."""

from __future__ import annotations

import argparse
import traceback
from typing import Any, Dict, List

from rag_service import available_providers, generate_answer, retrieve_context

from .utils import ARTIFACTS_DIR, DATA_DIR, ensure_dirs, load_json, utc_timestamp, write_json


DEFAULT_MODELS = {
    "groq": "llama-3.3-70b-versatile",
    "google": "gemini-2.5-flash",
}


def run_eval(dataset_path: str, top_k: int = 8, providers: List[str] | None = None) -> Dict[str, Any]:
    data = load_json(DATA_DIR / dataset_path if not dataset_path.startswith(":") and "\\" not in dataset_path and "/" not in dataset_path else dataset_path)
    questions = data["questions"]

    provider_flags = available_providers()
    providers = providers or ["groq", "google"]

    run_records: List[Dict[str, Any]] = []
    provider_summary: Dict[str, Any] = {}

    for provider in providers:
        provider_summary[provider] = {
            "available": bool(provider_flags.get(provider, False)),
            "model": DEFAULT_MODELS.get(provider),
            "num_success": 0,
            "num_failed": 0,
            "missing_key": not bool(provider_flags.get(provider, False)),
        }

    for q in questions:
        contexts = retrieve_context(q["question"], top_k=top_k)

        for provider in providers:
            model_name = DEFAULT_MODELS.get(provider)
            record = {
                "question_id": q["id"],
                "question": q["question"],
                "question_type": q["type"],
                "expected_in_corpus": bool(q["expected_in_corpus"]),
                "reference_answer": q["reference_answer"],
                "provider": provider,
                "model": model_name,
                "top_k": top_k,
                "contexts": contexts,
                "answer": None,
                "error": None,
            }

            if not provider_summary[provider]["available"]:
                record["error"] = f"Missing API key for provider: {provider}"
                provider_summary[provider]["num_failed"] += 1
                run_records.append(record)
                continue

            try:
                answer = generate_answer(q["question"], contexts, provider=provider, model=model_name)
                record["answer"] = answer
                provider_summary[provider]["num_success"] += 1
            except Exception as ex:
                record["error"] = str(ex)
                record["trace"] = traceback.format_exc(limit=1)
                provider_summary[provider]["num_failed"] += 1

            run_records.append(record)

    return {
        "metadata": {
            "created_at_utc": utc_timestamp(),
            "dataset_metadata": data.get("metadata", {}),
            "top_k": top_k,
            "providers": providers,
        },
        "provider_summary": provider_summary,
        "records": run_records,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run conversation evaluation across LLM providers")
    parser.add_argument("--dataset", default="conversation_eval_questions.json")
    parser.add_argument("--top-k", type=int, default=8)
    parser.add_argument("--providers", default="groq,google")
    parser.add_argument("--output", default="raw_model_outputs.json")
    args = parser.parse_args()

    ensure_dirs()
    providers = [p.strip() for p in args.providers.split(",") if p.strip()]
    payload = run_eval(dataset_path=args.dataset, top_k=args.top_k, providers=providers)

    out_path = ARTIFACTS_DIR / args.output
    write_json(out_path, payload)
    print(f"Raw outputs written: {out_path}")


if __name__ == "__main__":
    main()
