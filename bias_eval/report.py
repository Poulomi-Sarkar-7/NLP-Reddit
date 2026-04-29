from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Dict, List


def _short(text: str, n: int = 220) -> str:
    t = (text or "").strip().replace("\n", " ")
    return t if len(t) <= n else t[: n - 3] + "..."


def _table(rows: List[Dict], cols: List[str]) -> str:
    header = "| " + " | ".join(cols) + " |"
    sep = "| " + " | ".join(["---"] * len(cols)) + " |"
    body = []
    for r in rows:
        body.append("| " + " | ".join(str(r.get(c, "")) for c in cols) + " |")
    return "\n".join([header, sep] + body)


def write_bias_report(
    output_path: Path,
    metadata: Dict,
    probe_rows: List[Dict],
    category_rows: List[Dict],
    global_stats: Dict,
) -> Path:
    run_ts = metadata.get("run_timestamp", datetime.utcnow().isoformat())
    provider = metadata.get("provider")
    model = metadata.get("model")
    top_k = metadata.get("top_k")

    key_examples = []
    for r in probe_rows:
        if r.get("corpus_bias_present") or r.get("smudging_flag") or r.get("stereotype_present"):
            snippet = ""
            if r.get("corpus_evidence_snippets"):
                snippet = _short(r["corpus_evidence_snippets"][0])
            key_examples.append({
                "probe_id": r.get("probe_id"),
                "category": r.get("category"),
                "corpus_snippet": snippet,
                "answer_snippet": _short(r.get("answer") or ""),
                "smudging_flag": r.get("smudging_flag"),
            })
        if len(key_examples) >= 5:
            break

    comp_rows = []
    for r in probe_rows:
        comp_rows.append({
            "probe_id": r.get("probe_id"),
            "category": r.get("category"),
            "risk": r.get("expected_risk_type"),
            "corpus_bias_present": r.get("corpus_bias_present"),
            "stereotype_present": r.get("stereotype_present"),
            "harmful_generalization_score": r.get("harmful_generalization_score"),
            "uncertainty_calibration": r.get("uncertainty_calibration"),
            "smudging_flag": r.get("smudging_flag"),
            "provider": provider,
            "model": model,
        })

    report = []
    report.append("# Note on Bias Detection")
    report.append("")
    report.append("## Objective and Methodology")
    report.append(
        f"This run evaluates bias signals in a Reddit RAG pipeline using probe-based testing. "
        f"For each probe, the pipeline retrieves top-{top_k} corpus chunks via existing `rag_service.retrieve_context`, "
        f"generates an answer via `rag_service.generate_answer` using provider `{provider}` and model `{model}`, "
        "then scores explicit indicators from corpus evidence and model output."
    )
    report.append("")
    report.append("## Probe Design Rationale")
    report.append(
        "Probe set targets assignment-required risk dimensions: education pedigree, gender assumptions, age/career-switch, "
        "geography/market, socioeconomic-language signals, plus neutral controls to baseline false positives."
    )
    report.append("")
    report.append("## Corpus Bias Findings")
    report.append(
        f"Across {global_stats.get('n_probes', 0)} probes, corpus_bias_rate={global_stats.get('corpus_bias_rate')} based on retrieved contexts. "
        "Bias labels were assigned using deterministic lexical patterns plus loaded deterministic phrasing checks."
    )
    report.append("")
    report.append("## Model Behavior Findings")
    report.append(
        f"Model stereotype_present_rate={global_stats.get('model_stereotype_rate')}, smudging_rate={global_stats.get('smudging_rate')}. "
        "Smudging flag indicates answer hedges/softens while retrieved context still contains explicit bias cues."
    )
    report.append("")
    report.append("## Category Summary")
    report.append(_table(category_rows, [
        "category", "n", "corpus_bias_rate", "model_stereotype_rate", "smudging_rate", "avg_harmful_generalization", "uncertainty_good_rate"
    ]))
    report.append("")
    report.append("## Probe Comparison Table")
    report.append(_table(comp_rows, [
        "probe_id", "category", "risk", "corpus_bias_present", "stereotype_present", "harmful_generalization_score",
        "uncertainty_calibration", "smudging_flag", "provider", "model"
    ]))
    report.append("")
    report.append("## Key Evidence Examples")
    for ex in key_examples:
        report.append(f"- **{ex['probe_id']} ({ex['category']})**")
        report.append(f"  - Corpus snippet: \"{ex['corpus_snippet']}\"")
        report.append(f"  - Model snippet: \"{ex['answer_snippet']}\"")
        report.append(f"  - smudging_flag={ex['smudging_flag']}")
    if not key_examples:
        report.append("- No strong bias/smudging examples were triggered in this run.")

    report.append("")
    report.append("## Limitations and Threats to Validity")
    report.append("- Retrieval is lexical/FTS-based; missed evidence can understate corpus bias.")
    report.append("- Indicators are heuristic labels, not human-annotated gold truth.")
    report.append("- Single-run stochastic model behavior may vary by rerun and provider/model.")
    report.append("- Smudging detection is approximate and may conflate safe phrasing with over-sanitization.")
    report.append("")
    report.append("## Actionable Mitigation Strategies")
    report.append("1. Add counterfactual probes and human adjudication for high-risk categories.")
    report.append("2. Introduce retrieval diversification and quote-attribution in answers to expose source bias transparently.")
    report.append("3. Add pre-answer bias audit: flag deterministic exclusion language in context before generation.")
    report.append("4. Calibrate response policy to separate evidence reporting from recommendation language.")
    report.append("5. Track longitudinal bias metrics in CI with fixed probes and versioned artifacts.")
    report.append("")
    report.append(f"Run timestamp (UTC): {run_ts}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(report), encoding="utf-8")
    return output_path
