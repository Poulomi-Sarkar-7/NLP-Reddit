import re
import pandas as pd

SLANG_TERMS = {
    "AITA", "NTA", "YTA", "ESH", "NAH", "TLDR", "OP", "IMO", "IMHO", "AMA", "FYI", "SMH", "IDK", "TBH"
}

ORG_HINTS = {
    "Google", "Microsoft", "Amazon", "Meta", "OpenAI", "IIT", "NIT", "MIT", "Stanford", "Harvard", "Bangalore", "Bengaluru", "Delhi", "Mumbai", "Kolkata", "Pune", "Chennai", "Hyderabad"
}

CODE_MIX_RE = re.compile(r"[\u0980-\u09FF].*[A-Za-z]|[A-Za-z].*[\u0980-\u09FF]")


def has_code_mix(text: str) -> bool:
    if not isinstance(text, str):
        return False
    return bool(CODE_MIX_RE.search(text))


def has_slang(text: str) -> bool:
    if not isinstance(text, str):
        return False
    toks = re.findall(r"[A-Za-z]{2,}", text.upper())
    return any(t in SLANG_TERMS for t in toks)


def has_named_entity_like(text: str) -> bool:
    if not isinstance(text, str):
        return False
    words = re.findall(r"\b[A-Z][a-zA-Z]{2,}\b", text)
    if len(words) >= 2:
        return True
    return any(h in text for h in ORG_HINTS)


def tag_edge_cases(df: pd.DataFrame, source_col: str = "source_text") -> pd.DataFrame:
    out = df.copy()
    out["is_code_mixed"] = out[source_col].apply(has_code_mix)
    out["has_reddit_slang"] = out[source_col].apply(has_slang)
    out["has_named_entities"] = out[source_col].apply(has_named_entity_like)
    return out


def segment_performance(df_tagged: pd.DataFrame, per_row_with_row_id: pd.DataFrame, system_col: str) -> pd.DataFrame:
    merged = per_row_with_row_id.merge(
        df_tagged[["row_id", "is_code_mixed", "has_reddit_slang", "has_named_entities"]],
        on="row_id",
        how="left",
    )
    merged = merged[merged["system"] == system_col].copy()

    segments = ["is_code_mixed", "has_reddit_slang", "has_named_entities"]
    metric_cols = ["chrf", "bleu", "rouge1_f", "rouge2_f", "rougeL_f", "bertscore_f1"]
    rows = []
    for seg in segments:
        for val in [True, False]:
            g = merged[merged[seg] == val]
            row = {"system": system_col, "segment": seg, "segment_value": val, "count": int(len(g))}
            for m in metric_cols:
                vals = g[m].dropna()
                row[f"{m}_mean"] = float(vals.mean()) if len(vals) else None
            rows.append(row)
    return pd.DataFrame(rows)


def qualitative_examples(df_tagged: pd.DataFrame, sample_n: int = 2) -> pd.DataFrame:
    rows = []
    for seg in ["is_code_mixed", "has_reddit_slang", "has_named_entities"]:
        s = df_tagged[df_tagged[seg] == True].head(sample_n)
        for _, r in s.iterrows():
            rows.append({
                "row_id": r["row_id"],
                "segment": seg,
                "source_text": str(r["source_text"]),
                "ground_truth_bengali": str(r["ground_truth_bengali"]),
                "groq_translation": str(r.get("groq_translation", "")),
                "gemini_translation": str(r.get("gemini_translation", "")),
            })
    return pd.DataFrame(rows)
