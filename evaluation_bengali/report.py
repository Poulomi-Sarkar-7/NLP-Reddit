from pathlib import Path
import pandas as pd
from metrics import markdown_table, sanitize_for_report


def _fmt(v, nd=4):
    if pd.isna(v):
        return "NA"
    return f"{v:.{nd}f}"


def render_report(
    out_path: Path,
    run_ts: str,
    validation_summary: dict,
    aggregate_df: pd.DataFrame,
    segment_df: pd.DataFrame,
    manual_df: pd.DataFrame,
    examples_df: pd.DataFrame,
    gemini_mode: str,
):
    lines = []
    lines.append("# Bengali Translation Evaluation Report")
    lines.append("")
    lines.append(f"- Run timestamp: `{run_ts}`")
    lines.append(f"- Input rows: `{validation_summary.get('row_count', 'NA')}`")
    lines.append(f"- Gemini mode: `{gemini_mode}`")
    lines.append("")

    lines.append("## Task Setup")
    lines.append("- Dataset: `bengali_translation.csv` with source, reference Bengali, and system outputs.")
    lines.append("- Systems evaluated: Groq and Gemini columns.")
    lines.append("")

    lines.append("## Methodology")
    lines.append("- Data validation for required columns, IDs, missingness, and row integrity.")
    lines.append("- Missing Groq translations generated via API with retries and checkpointing.")
    lines.append("- Gemini attempted via API; fallback path used only when API unavailable.")
    lines.append("- Metrics: chrF, BLEU, ROUGE-1/2/L F1, and BERTScore F1 (multilingual model).")
    lines.append("- Segment analysis for code-mixed text, Reddit slang, and named-entity-heavy inputs.")
    lines.append("")

    lines.append("## Validation Summary")
    lines.append("```json")
    lines.append(pd.Series(validation_summary).to_json(indent=2))
    lines.append("```")
    lines.append("")

    lines.append("## Aggregate Metrics")
    if not aggregate_df.empty:
        lines.append(markdown_table(aggregate_df))
    else:
        lines.append("_No aggregate metrics available._")
    lines.append("")

    lines.append("## Segment Performance")
    if not segment_df.empty:
        lines.append(markdown_table(segment_df))
    else:
        lines.append("_No segment metrics available._")
    lines.append("")

    lines.append("## Manual Evaluation Sheet (Auto-Filled)")
    lines.append("- Fluency and adequacy are auto-filled on a 1-5 scale from metric-driven heuristics.")
    if not manual_df.empty:
        lines.append(markdown_table(manual_df))
    else:
        lines.append("_No manual sheet rows generated._")
    lines.append("")

    lines.append("## Qualitative Edge-Case Examples")
    if not examples_df.empty:
        ex = examples_df.copy()
        for c in ["source_text", "ground_truth_bengali", "groq_translation", "gemini_translation"]:
            ex[c] = ex[c].apply(sanitize_for_report)
        lines.append(markdown_table(ex))
    else:
        lines.append("_No edge-case examples found._")
    lines.append("")

    lines.append("## Conclusion")
    lines.append("The pipeline completed end-to-end with reproducible artifacts, system-level metrics, and edge-case diagnostics.")
    lines.append("Performance trends should be interpreted jointly using chrF, semantic similarity, and segment-specific behavior.")

    out_path.write_text("\n".join(lines), encoding="utf-8")
