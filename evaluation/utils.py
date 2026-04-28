"""Utilities for conversation evaluation pipeline."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List

EVAL_ROOT = Path(__file__).resolve().parent
DATA_DIR = EVAL_ROOT / "data"
ARTIFACTS_DIR = EVAL_ROOT / "artifacts"
REPORTS_DIR = EVAL_ROOT / "reports"


def ensure_dirs() -> None:
    for path in (DATA_DIR, ARTIFACTS_DIR, REPORTS_DIR):
        path.mkdir(parents=True, exist_ok=True)


def utc_timestamp() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_ws(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


def token_set(text: str) -> set[str]:
    return set(re.findall(r"\b[a-zA-Z][a-zA-Z0-9+\-]{2,}\b", (text or "").lower()))


def chunked(iterable: Iterable[Any], size: int) -> List[List[Any]]:
    bucket: List[Any] = []
    out: List[List[Any]] = []
    for item in iterable:
        bucket.append(item)
        if len(bucket) == size:
            out.append(bucket)
            bucket = []
    if bucket:
        out.append(bucket)
    return out
