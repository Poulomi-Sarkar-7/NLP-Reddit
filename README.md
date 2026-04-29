# NLP_Reddit

This repository contains the full NLP project pipeline and dashboard for Reddit data (`r/cscareerquestions`), including Part 1 analytics, Part 2 RAG conversation/translation systems, evaluations, and reports.

## 1. Project at a glance

- **Raw data source**: `career.db`
- **Main analytics DB used by dashboard topic APIs**: `career_processed3.db`
- **RAG retrieval index DB**: `career_rag.db`
- **Backend server**: `server.py` (Flask API)
- **Frontend dashboard**: `frontend/` (React + Vite)

---

## 2. Root directory structure and file purposes

```text
NLP_Reddit/
+- .env
+- .gitignore
+- README.md
+- env_utils.py
+- server.py
+- nlp_pipeline.py
+- rag_service.py
+- career.py
+- career.db
+- career_processed3.db
+- career_rag.db
+- bias_eval/
+- evaluation/
+- evaluation_bengali/
+- frontend/
+- images/
+- reports/
```

### Root files

- **`.env`**
  - Local environment variables (API keys, etc.).
  - Typical keys used in this project:
    - `GROQ_API_KEY`
    - `GOOGLE_API_KEY` (or `GEMINI_API_KEY`)

- **`.gitignore`**
  - Ignore rules for local/private/generated files. ENV is here

- **`README.md`**
  - This documentation file.

- **`env_utils.py`**
  - Lightweight `.env` loader used by Python modules.

- **`server.py`**
  - Main Flask backend.
  - Exposes APIs for:
    - dashboard stats
    - topics/timelines
    - topic detail + stance + profanity
    - users, keywords, sorting
    - conversation (RAG)
    - translation
    - reports PDF listing/serving

- **`nlp_pipeline.py`**
  - Offline processing pipeline script (topic modeling, stance enrichment, summaries, trend labels).
  - Generates processed DB outputs.

- **`rag_service.py`**
  - RAG logic:
    - chunking
    - indexing into `career_rag.db`
    - retrieval
    - prompt building
    - LLM answer generation
    - knowledge-graph extraction/expansion helpers

- **`career.py`**
  - Data-related helper script from earlier collection/processing phase.

### Databases

- **`career.db`** (raw)
  - Original scraped Reddit posts/comments.
  - Used by:
    - raw totals in dashboard
    - user lookup
    - keyword analysis
    - translation post search
    - building RAG index

- **`career_processed3.db`** (active processed analytics DB)
  - Used by topic/timeline/topic-detail analytics APIs.
  - Contains processed topic tables (`topics`, `topic_volumes`, `comment_stances`, etc.).

- **`career_rag.db`** (active retrieval DB)
  - Chunk store + FTS index for conversation system retrieval.

> Note: Older processed DB variants from prior runs may exist in some local setups; current server connection points to `career_processed3.db` for topic analytics.

---

## 3. Backend folders

### `bias_eval/`
Bias detection evaluation pipeline and outputs.

- `run_bias_eval.py`  main runner for bias evaluation.
- `scoring.py`  bias scoring logic.
- `report.py`  report generation.
- `probes.json`  evaluation probe set.
- `artifacts/<timestamp>/`  generated run outputs (CSV/JSON/markdown report).
- `README.md`  module-specific notes.

### `evaluation/`
Conversation/RAG evaluation scripts and artifacts.

- `run_conversation_eval.py`  evaluation entry point.
- `runner.py`, `scorer.py`, `dataset_builder.py`, `report_generator.py`, `utils.py`  evaluation pipeline modules.
- `data/conversation_eval_questions.json`  evaluation question set.
- `artifacts/`  generated metrics/output files.
- `reports/`  generated evaluation report files.
- `requirements-eval.txt`  optional eval dependencies.
- `README.md`  evaluation usage details.

### `evaluation_bengali/`
Bengali translation evaluation workflow.

- `run_bengali_translation_eval.py`  main evaluator.
- `metrics.py`, `report.py`, `edge_cases.py`  scoring/report support.
- `bengali_translation.csv`  input set.
- `inputs/` cleaned/prepared inputs.
- `artifacts/<timestamp>/`  per-run outputs (metrics, logs, reports).

---

## 4. Frontend (`frontend/`)

React + Vite dashboard.

```text
frontend/
+- package.json / package-lock.json
+- vite.config.js
+- index.html
+- eslint.config.js
+- public/
+- favicon.svg
+- icons.svg
+- src/
   +- main.jsx
   +- App.jsx
   +- App.css
   +- index.css
   +- assets/
      +- dash1.jpg, dash2.jpg
      +- card1.jpg, card2.jpg
      +- (other static assets)
   +- pages/
      +- Home.jsx
      +- Topics.jsx
      +- TopicDetail.jsx
      +- ConsolidatedTimeline.jsx
      +- ConversationSystem.jsx
      +- Translation.jsx
      +- Users.jsx
      +- Keywords.jsx
      +- Sorting.jsx
      +- Reports.jsx
```

### Key frontend page responsibilities

- **Home**  overview/stats + hero visuals.
- **Topics / TopicDetail / ConsolidatedTimeline**  Part 1 topic analytics.
- **ConversationSystem**  RAG Q&A + knowledge graph.
- **Translation**  Bengali translation of queried post text.
- **Users**  user lookup + top user activity chart.
- **Keywords**  keyword frequency, co-occurrence, heatmap, matching snippets.
- **Sorting**  sortable topic ranking by selected metric.
- **Reports**  label-based report viewer for PDFs.

---

## 5. Reports and static assets

### `reports/`
Final report PDFs shown in the Reports page:

- `Part1_Documentation and Dashboard.pdf`
- `rag_evaluation_report.pdf`
- `bengali_translation_evaluation_report.pdf`
- `bias_detection_report.pdf`
- `ethics_note.pdf`
- `FullFinalReport.pdf`

### `images/`
Design/source images used for dashboard assets (light/dark variants, etc.).

---

## 6. Which components are used in runtime

- **Backend app entry**: `python server.py`
- **Frontend app entry**: `frontend/src/main.jsx` via Vite
- **Primary DBs at runtime**:
  - `career.db` (raw operations)
  - `career_processed3.db` (topic analytics)
  - `career_rag.db` (conversation retrieval)

---

## 7. Quick run notes

1. Set API keys in `.env`.
2. Start backend:
   ```bash
   python server.py
   ```
3. Start frontend:
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

