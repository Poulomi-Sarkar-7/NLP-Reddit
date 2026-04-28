# Conversation System Evaluation

This module implements assignment Part 2 "Conversation System Evaluation" end-to-end using existing project RAG functions in `rag_service.py`.

## What It Produces

- `evaluation/data/conversation_eval_questions.json`
- `evaluation/artifacts/raw_model_outputs.json`
- `evaluation/artifacts/per_sample_scores.json`
- `evaluation/artifacts/per_sample_scores.csv`
- `evaluation/artifacts/aggregate_metrics.json`
- `evaluation/artifacts/aggregate_metrics.csv`
- `evaluation/reports/conversation_system_evaluation_report.docx`

## Dataset Design

- 18 curated questions (>=15 required)
- Includes factual and opinion-summary questions
- Includes 3 adversarial questions not present in corpus
- Structured fields:
  - `id`
  - `question`
  - `type`
  - `reference_answer`
  - `expected_in_corpus`

## Metrics

- BLEU
- ROUGE-L
- BERTScore (F1)
- Faithfulness flag (deterministic heuristic)
- Extra diagnostics:
  - support ratio
n  - unsupported sentence ratio
  - adversarial refusal percentage

## Faithfulness Heuristic

Each sample is marked faithful (`1`) or not (`0`) by checking generated answer against retrieved context:

1. Compute content-token lexical support ratio between answer and retrieved context.
2. Split answer into factual sentences and compute best sentence-level Jaccard overlap with context sentences.
3. Flag low-overlap sentences as unsupported.
4. In-corpus question faithfulness rule:
   - support ratio >= 0.55
   - unsupported sentence ratio <= 0.40
5. Adversarial question faithfulness rule:
   - model abstains (missing-evidence phrasing), or very low lexical grounding for factual claims.

## One-Command Run

```bash
python -m pip install -r evaluation/requirements-eval.txt
python -m evaluation.run_conversation_eval
```

Optional:

```bash
python -m evaluation.run_conversation_eval --top-k 8 --providers groq,google
```

## Notes

- The pipeline reuses `retrieve_context` and `generate_answer` from `rag_service.py`.
