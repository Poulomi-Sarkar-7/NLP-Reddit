"""Build a curated evaluation dataset for conversation system testing."""

from __future__ import annotations

import argparse
import re
from typing import Any, Dict, List

from rag_service import retrieve_context

from .utils import DATA_DIR, ensure_dirs, normalize_ws, write_json, utc_timestamp


DATASET_PATH = DATA_DIR / "conversation_eval_questions.json"


QUESTION_BLUEPRINTS: List[Dict[str, Any]] = [
    {"id": "Q01", "type": "factual", "expected_in_corpus": True, "question": "What are users saying about the current software job market difficulty in the US?"},
    {"id": "Q02", "type": "opinion-summary", "expected_in_corpus": True, "question": "How do people compare stability versus growth when choosing between job offers?"},
    {"id": "Q03", "type": "factual", "expected_in_corpus": True, "question": "What common resume or interview preparation concerns appear in recent discussions?"},
    {"id": "Q04", "type": "opinion-summary", "expected_in_corpus": True, "question": "What concerns do users express about AI-generated resumes and job applications?"},
    {"id": "Q05", "type": "factual", "expected_in_corpus": True, "question": "What tradeoffs are mentioned between consulting roles and large-company roles like IBM?"},
    {"id": "Q06", "type": "opinion-summary", "expected_in_corpus": True, "question": "How are layoffs and hiring slowdowns described by community members?"},
    {"id": "Q07", "type": "factual", "expected_in_corpus": True, "question": "What do users mention about early-career struggles after a CS degree?"},
    {"id": "Q08", "type": "opinion-summary", "expected_in_corpus": True, "question": "What are attitudes toward using LLM coding assistants at work?"},
    {"id": "Q09", "type": "factual", "expected_in_corpus": True, "question": "What geographic comparisons are discussed for tech jobs outside the US versus inside the US?"},
    {"id": "Q10", "type": "opinion-summary", "expected_in_corpus": True, "question": "What arguments appear when people debate compensation versus work-life balance?"},
    {"id": "Q11", "type": "factual", "expected_in_corpus": True, "question": "What recurring advice is shared for applicants receiving very few interview callbacks?"},
    {"id": "Q12", "type": "opinion-summary", "expected_in_corpus": True, "question": "How do users frame whether product management is growing because of LLM tooling?"},
    {"id": "Q13", "type": "factual", "expected_in_corpus": True, "question": "What concerns are raised about perfect-candidate signaling during job applications?"},
    {"id": "Q14", "type": "opinion-summary", "expected_in_corpus": True, "question": "What themes appear in posts about deciding between multiple offers?"},
    {"id": "Q15", "type": "factual", "expected_in_corpus": True, "question": "What user-reported indicators suggest that market recovery has or has not started?"},
    {"id": "Q16", "type": "adversarial", "expected_in_corpus": False, "question": "Who won the 2026 FIFA World Cup and how did it impact software hiring?"},
    {"id": "Q17", "type": "adversarial", "expected_in_corpus": False, "question": "What is OpenAI's internal Q4 2026 recruiting budget for ML engineers?"},
    {"id": "Q18", "type": "adversarial", "expected_in_corpus": False, "question": "Give the private phone number of the subreddit moderators for direct referrals."},
]


def _split_sentences(text: str) -> List[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text or "") if s.strip()]


def _reference_from_contexts(contexts: List[Dict[str, Any]], question: str) -> str:
    if not contexts:
        return "The corpus does not provide enough evidence to answer this question."

    keyword_tokens = set(re.findall(r"\b[a-zA-Z]{4,}\b", question.lower()))
    ranked: List[tuple[float, str]] = []
    for ctx in contexts[:6]:
        body = normalize_ws(ctx.get("body", ""))
        for sent in _split_sentences(body):
            sent_tokens = set(re.findall(r"\b[a-zA-Z]{4,}\b", sent.lower()))
            overlap = len(keyword_tokens & sent_tokens)
            score = overlap + (2.0 if len(sent_tokens) > 8 else 0.0)
            ranked.append((score, sent))

    ranked.sort(key=lambda x: x[0], reverse=True)
    picks: List[str] = []
    seen = set()
    for _, sent in ranked:
        norm = sent.lower()
        if norm in seen:
            continue
        seen.add(norm)
        picks.append(sent)
        if len(picks) == 3:
            break

    if not picks:
        return "The retrieved Reddit chunks contain partial evidence but no direct summary sentence."

    return " ".join(picks)


def build_dataset(top_k: int = 8) -> Dict[str, Any]:
    rows: List[Dict[str, Any]] = []

    for blueprint in QUESTION_BLUEPRINTS:
        question = blueprint["question"]
        expected = bool(blueprint["expected_in_corpus"])

        contexts = retrieve_context(question, top_k=top_k) if expected else []
        if expected:
            reference_answer = _reference_from_contexts(contexts, question)
        else:
            reference_answer = (
                "This information is outside the Reddit corpus. A grounded system should explicitly state that "
                "the answer is unavailable in retrieved subreddit data."
            )

        rows.append(
            {
                "id": blueprint["id"],
                "question": question,
                "type": blueprint["type"],
                "reference_answer": reference_answer,
                "expected_in_corpus": expected,
            }
        )

    return {
        "metadata": {
            "name": "r_cscareerquestions_conversation_eval",
            "created_at_utc": utc_timestamp(),
            "num_questions": len(rows),
            "notes": "Reference answers for in-corpus questions are deterministic extractive summaries of retrieved chunks.",
        },
        "questions": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build conversation evaluation dataset")
    parser.add_argument("--top-k", type=int, default=8)
    parser.add_argument("--output", default=str(DATASET_PATH))
    args = parser.parse_args()

    ensure_dirs()
    payload = build_dataset(top_k=args.top_k)
    out_path = DATASET_PATH if args.output == str(DATASET_PATH) else DATA_DIR / args.output
    write_json(out_path, payload)
    print(f"Dataset written: {out_path}")


if __name__ == "__main__":
    main()
