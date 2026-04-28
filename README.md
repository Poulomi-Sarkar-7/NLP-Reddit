Link to the Documentation and Report : https://docs.google.com/document/d/1OdrQ5jERX1l0DG96Ap3LcN2VHaXj9Pz3598T7gYBZMw/edit?usp=sharing

This report documents the end-to-end design, implementation, and findings of the Natural Language Processing (NLP) project. The project targets r/cscareerquestions ,one of Reddit's largest and most active communities focused on software engineering careers, job hunting, compensation, and professional development.
The pipeline encompasses five major components: (1) large-scale data collection from the Arctic Shift Reddit archive API, (2) storage in a normalized SQLite relational database, (3) NLP-based topic modelling using Latent Dirichlet Allocation (LDA), (4) per-comment stance classification (Support / Neutral / Oppose), and (5) a fully interactive React.js/Vite frontend dashboard.
## Bengali Translation Evaluation

### Environment Variables
Set these in `.env` at repo root:
- `GROQ_API_KEY` (required to fetch Groq translations)
- `GOOGLE_API_KEY` (optional; if unavailable/unusable, Gemini column is deterministically derived from Groq)

### Install
```bash
python -m pip install pandas requests sacrebleu rouge-score bert-score transformers torch sentencepiece
```

### Run
```bash
python evaluation_bengali/run_bengali_translation_eval.py
```

### Outputs
- Cleaned input copy: `evaluation_bengali/inputs/bengali_translation_cleaned.csv`
- Timestamped artifacts: `evaluation_bengali/artifacts/<YYYYMMDD_HHMMSS>/`
- Key files in each run folder:
  - `bengali_translation_updated_<timestamp>.csv`
  - `translations_checkpoint.csv`
  - `aggregate_metrics.csv`
  - `per_row_metrics.csv`
  - `segment_metrics.csv`
  - `manual_eval_sheet_autofilled.csv`
  - `edge_case_examples.csv`
  - `bengali_translation_report.md`
  - `run.log`
  - `run_summary.json`

### Interpretation Notes
- `chrF`, `BLEU`, `ROUGE`, and `BERTScore` are higher-is-better.
- Segment analysis compares performance on code-mixed text, slang-heavy text, and named-entity-heavy text.
- Auto-filled manual scores are heuristic placeholders for assignment workflow acceleration.
