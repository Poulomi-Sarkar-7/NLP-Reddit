from __future__ import annotations

import json
import math
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak

ROOT = Path(r"D:\Sem 6\NLP\NLP_Reddit")
DATASET = ROOT / "evaluation" / "data" / "conversation_eval_questions.json"
PER_SAMPLE = ROOT / "evaluation" / "artifacts" / "per_sample_scores.json"
AGG = ROOT / "evaluation" / "artifacts" / "aggregate_metrics.json"
OUT = ROOT / "evaluation" / "reports" / "conversation_system_evaluation_clean.pdf"

COLOR_H1 = colors.HexColor("#853953")
COLOR_H2 = colors.HexColor("#ab4b6d")
COLOR_TEXT = colors.black


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def fmt(v):
    if v is None:
        return "Failed"
    if isinstance(v, float):
        if math.isnan(v):
            return "Failed"
        return f"{v:.4f}"
    return str(v)


def build():
    dataset = load_json(DATASET)
    per_sample = load_json(PER_SAMPLE)["rows"]
    aggregate = load_json(AGG)["rows"]

    by_q = {q["id"]: q for q in dataset["questions"]}

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("TitleCustom", parent=styles["Heading1"], fontName="Helvetica-Bold", fontSize=18, textColor=COLOR_H1, spaceAfter=10)
    h2_style = ParagraphStyle("H2Custom", parent=styles["Heading2"], fontName="Helvetica-Bold", fontSize=13, textColor=COLOR_H2, spaceBefore=8, spaceAfter=6)
    body_style = ParagraphStyle("BodyCustom", parent=styles["BodyText"], fontName="Helvetica", fontSize=10, leading=14, textColor=COLOR_TEXT)

    doc = SimpleDocTemplate(str(OUT), pagesize=A4, rightMargin=1.2*cm, leftMargin=1.2*cm, topMargin=1.2*cm, bottomMargin=1.2*cm)
    story = []

    story.append(Paragraph("Conversation System Evaluation Report", title_style))
    story.append(Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", body_style))
    story.append(Spacer(1, 8))

    story.append(Paragraph("Task", h2_style))
    story.append(Paragraph("Evaluate a RAG-based conversation system over r/cscareerquestions using at least 15 curated QA items across factual, opinion-summary, and adversarial categories; compare two LLM providers; compute automated quality metrics; and summarize model behavior.", body_style))

    story.append(Paragraph("What Was Done", h2_style))
    done_lines = [
        "Created a curated evaluation dataset with 18 questions and reference answers.",
        "Ran retrieval + answer generation through existing project RAG pipeline for Groq and Google/Gemini.",
        "Computed BLEU, ROUGE-L, BERTScore(F1), and deterministic faithfulness flags.",
        "Produced per-question and aggregate evaluation artifacts.",
    ]
    for d in done_lines:
        story.append(Paragraph(f"- {d}", body_style))

    story.append(Paragraph("Methodology", h2_style))
    meth = [
        "Retrieval: Existing retrieve_context() from rag_service.py with top-k context chunks.",
        "Generation: Existing generate_answer() from rag_service.py for each provider/model.",
        "References: Deterministic extractive summaries from retrieved corpus chunks for in-corpus questions; explicit abstention references for adversarial questions.",
        "Faithfulness: Binary heuristic using lexical support ratio and unsupported-sentence ratio against retrieved context.",
    ]
    for m in meth:
        story.append(Paragraph(f"- {m}", body_style))

    story.append(PageBreak())
    story.append(Paragraph("Evaluation Questions and Reference Answers", h2_style))

    q_rows = [["ID", "Type", "Question", "Reference Answer"]]
    for q in dataset["questions"]:
        q_rows.append([q["id"], q["type"], q["question"], q["reference_answer"]])

    q_table = Table(q_rows, colWidths=[1.2*cm, 2.5*cm, 6.0*cm, 9.6*cm], repeatRows=1)
    q_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f4dce5")),
        ("TEXTCOLOR", (0, 0), (-1, 0), COLOR_H1),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#d8b9c5")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("TEXTCOLOR", (0, 1), (-1, -1), COLOR_TEXT),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(q_table)

    story.append(PageBreak())
    story.append(Paragraph("Model Comparison (Aggregate Scores)", h2_style))

    a_rows = [["Provider", "Model", "BLEU", "ROUGE-L", "BERTScore(F1)", "Faithfulness %", "Questions", "Failed"]]
    for a in aggregate:
        a_rows.append([
            a["provider"],
            a["model"],
            fmt(a.get("bleu")),
            fmt(a.get("rougeL")),
            fmt(a.get("bertscore_f1")),
            fmt(a.get("faithfulness_pct")),
            str(a.get("num_questions", "")),
            str(a.get("num_failed", "")),
        ])

    a_table = Table(a_rows, colWidths=[2.0*cm, 4.2*cm, 2.0*cm, 2.0*cm, 2.4*cm, 2.4*cm, 1.8*cm, 1.6*cm], repeatRows=1)
    a_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f4dce5")),
        ("TEXTCOLOR", (0, 0), (-1, 0), COLOR_H1),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#d8b9c5")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TEXTCOLOR", (0, 1), (-1, -1), COLOR_TEXT),
        ("ALIGN", (2, 1), (-1, -1), "CENTER"),
    ]))
    story.append(a_table)

    story.append(Spacer(1, 8))
    story.append(Paragraph("Per-Question Score Table", h2_style))

    ps_rows = [["QID", "Type", "Provider", "BLEU", "ROUGE-L", "BERTScore", "Faithful"]]
    per_sample_sorted = sorted(per_sample, key=lambda r: (r["question_id"], r["provider"]))
    for r in per_sample_sorted:
        bleu = "Failed" if r.get("error") else fmt(r.get("bleu"))
        rouge = "Failed" if r.get("error") else fmt(r.get("rougeL"))
        bert = "Failed" if r.get("error") else fmt(r.get("bertscore_f1"))
        faithful = "Failed" if r.get("error") else str(r.get("faithful"))
        ps_rows.append([r["question_id"], r["question_type"], r["provider"], bleu, rouge, bert, faithful])

    ps_table = Table(ps_rows, colWidths=[1.1*cm, 2.6*cm, 2.0*cm, 2.3*cm, 2.3*cm, 2.6*cm, 2.0*cm], repeatRows=1)
    ps_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f4dce5")),
        ("TEXTCOLOR", (0, 0), (-1, 0), COLOR_H1),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#d8b9c5")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("TEXTCOLOR", (0, 1), (-1, -1), COLOR_TEXT),
        ("ALIGN", (3, 1), (-1, -1), "CENTER"),
    ]))
    story.append(ps_table)

    story.append(PageBreak())
    story.append(Paragraph("Results", h2_style))
    for a in aggregate:
        story.append(Paragraph(
            f"- {a['provider']} ({a['model']}): BLEU {fmt(a.get('bleu'))}, ROUGE-L {fmt(a.get('rougeL'))}, "
            f"BERTScore(F1) {fmt(a.get('bertscore_f1'))}, Faithfulness {fmt(a.get('faithfulness_pct'))}%.",
            body_style,
        ))

    story.append(Paragraph("Key Observations", h2_style))
    obs = [
        "Groq completed all 18 questions, while Google had several failed entries in this run and is marked as Failed at sample level where applicable.",
        "Across successful outputs, semantic similarity (BERTScore) is stronger than lexical overlap (BLEU/ROUGE), indicating paraphrastic answers.",
        "Faithfulness remains the primary weakness: many responses include claims that are weakly supported by retrieved evidence.",
        "Adversarial handling is inconsistent; explicit abstention behavior should be improved for non-corpus questions.",
    ]
    for o in obs:
        story.append(Paragraph(f"- {o}", body_style))

    doc.build(story)
    print(f"PDF generated: {OUT}")


if __name__ == "__main__":
    build()
