# Bias Evaluation Pipeline (`bias_eval/`)

This folder contains an end-to-end, reproducible bias detection workflow for the Reddit RAG project.

## What It Covers

- Probe-based evaluation for assignment-required bias dimensions:
  - education pedigree bias
  - gender assumptions in tech careers
  - age/career-switch bias
  - geography/market bias
  - socioeconomic-language signals
  - neutral controls
- Corpus-side bias cues from retrieved contexts
- Model-answer bias and possible smudging/over-sanitization behavior

## Files

- `bias_eval/probes.json`: structured probe set (13 probes)
- `bias_eval/run_bias_eval.py`: one-command runner
- `bias_eval/scoring.py`: deterministic indicator logic
- `bias_eval/report.py`: markdown report generation
- `bias_eval/artifacts/<timestamp>/...`: run outputs

## Prerequisites

1. Python environment with project dependencies used by `rag_service.py`.
2. Existing project databases at repo root (`career.db`, `career_rag.db`).
3. At least one provider key in `.env`:
   - `GROQ_API_KEY` or
   - `GOOGLE_API_KEY` / `GEMINI_API_KEY`

If no provider key is available, retrieval and scoring still run, but model answers are unavailable and limitations are recorded.

## Run

```bash
python bias_eval/run_bias_eval.py
```

Optional:

```bash
python bias_eval/run_bias_eval.py --top-k 10 --provider groq
python bias_eval/run_bias_eval.py --top-k 10 --provider google
```

## Outputs

Each run writes a timestamped folder:

- `bias_eval/artifacts/<YYYYMMDD_HHMMSS>/raw_outputs.json`
- `bias_eval/artifacts/<YYYYMMDD_HHMMSS>/scored_results.csv`
- `bias_eval/artifacts/<YYYYMMDD_HHMMSS>/category_summary.csv`
- `bias_eval/artifacts/<YYYYMMDD_HHMMSS>/bias_detection_report.md`

## Interpretation Notes

- `corpus_bias_present`: whether retrieved corpus chunks showed explicit lexical bias cues.
- `stereotype_present`: whether model answer contains stereotype-like deterministic phrasing.
- `harmful_generalization_score`: model-level severity (0/1/2).
- `uncertainty_calibration`: `good` when answer shows calibrated uncertainty language; else `weak`.
- `smudging_flag`: model may be softening/hedging while retrieved context still contains bias cues.

These indicators are deterministic heuristics for assignment analysis and should be treated as audit signals, not final ground truth.
