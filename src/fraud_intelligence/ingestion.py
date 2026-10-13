"""Offline document loading and deterministic validation for Module 5."""

from __future__ import annotations

import json
from pathlib import Path
import re
import unicodedata

from .contracts import FraudIntelligenceDocument, validate_document_set


def normalize_text(text: str) -> str:
    """Normalize Unicode and whitespace while preserving textual meaning."""

    text = unicodedata.normalize("NFC", text).replace("\r\n", "\n").replace("\r", "\n")
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.split("\n")]
    return "\n".join(lines).strip()


def load_documents(path: str | Path) -> tuple[FraudIntelligenceDocument, ...]:
    """Load JSON array/object or JSONL and apply all Stage 1 validation."""

    source = Path(path)
    if source.suffix.lower() == ".jsonl":
        records = [json.loads(line) for line in source.read_text(encoding="utf-8").splitlines() if line.strip()]
    elif source.suffix.lower() == ".json":
        value = json.loads(source.read_text(encoding="utf-8"))
        records = value if isinstance(value, list) else value.get("documents") if isinstance(value, dict) else None
        if records is None:
            raise ValueError("JSON input must be an array or an object with documents")
    else:
        raise ValueError("document input must use .json or .jsonl")
    try:
        documents = tuple(FraudIntelligenceDocument(**record) for record in records)
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid fraud-intelligence document: {exc}") from exc
    documents = validate_document_set(documents)
    normalized = {}
    for document in documents:
        digest = normalize_text(document.content)
        if digest in normalized:
            raise ValueError(f"duplicate normalized content: {document.document_id} and {normalized[digest]}")
        normalized[digest] = document.document_id
    return documents
