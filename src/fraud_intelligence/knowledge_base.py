"""Deterministic chunking and atomic knowledge-base publication."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
from typing import Any

from .contracts import CONTRACT_SCHEMA_VERSION, FraudIntelligenceDocument
from .ingestion import load_documents, normalize_text


KNOWLEDGE_BASE_SCHEMA_VERSION = "module5_stage2_knowledge_base_v1"


@dataclass(frozen=True)
class KnowledgeBaseChunk:
    chunk_id: str
    document_id: str
    passage: str
    start_offset: int
    end_offset: int
    source_organization: str
    source_url: str
    source_type: str
    knowledge_base_version: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "chunk_id": self.chunk_id, "document_id": self.document_id,
            "passage": self.passage, "start_offset": self.start_offset,
            "end_offset": self.end_offset, "source_organization": self.source_organization,
            "source_url": self.source_url, "source_type": self.source_type,
            "knowledge_base_version": self.knowledge_base_version,
        }


def chunk_document(document: FraudIntelligenceDocument, *, max_chars: int = 500) -> tuple[KnowledgeBaseChunk, ...]:
    """Split normalized text at whitespace boundaries and retain offsets."""

    if max_chars < 1:
        raise ValueError("max_chars must be positive")
    text = normalize_text(document.content)
    chunks: list[KnowledgeBaseChunk] = []
    start = 0
    while start < len(text):
        limit = min(start + max_chars, len(text))
        end = limit
        if limit < len(text):
            boundary = text.rfind(" ", start, limit + 1)
            if boundary > start:
                end = boundary
        passage = text[start:end]
        if not passage:
            end = min(start + max_chars, len(text)); passage = text[start:end]
        chunk_id = hashlib.sha256(f"{document.document_id}:{start}:{end}:{passage}".encode("utf-8")).hexdigest()[:24]
        chunks.append(KnowledgeBaseChunk(chunk_id, document.document_id, passage, start, end, document.source_organization, document.source_url, document.source_type, document.knowledge_base_version))
        start = end
        while start < len(text) and text[start] == " ":
            start += 1
    return tuple(chunks)


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _write_atomic(path: Path, content: str) -> None:
    temporary = path.with_name(path.name + ".tmp")
    try:
        temporary.write_text(content, encoding="utf-8", newline="\n")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def build_knowledge_base(input_path: str | Path, output_dir: str | Path, *, knowledge_base_version: str, max_chars: int = 500) -> dict[str, Any]:
    """Validate, chunk, and atomically publish a versioned knowledge base."""

    if not isinstance(knowledge_base_version, str) or not knowledge_base_version.strip():
        raise ValueError("knowledge_base_version must be non-empty")
    destination = Path(output_dir)
    if destination.exists():
        raise FileExistsError(destination)
    documents = load_documents(input_path)
    if any(document.knowledge_base_version != knowledge_base_version for document in documents):
        raise ValueError("document knowledge-base versions do not match requested version")
    chunks = tuple(chunk for document in documents for chunk in chunk_document(document, max_chars=max_chars))
    chunk_ids = [chunk.chunk_id for chunk in chunks]
    if len(chunk_ids) != len(set(chunk_ids)):
        raise ValueError("duplicate chunk identifiers")
    temp_dir = Path(tempfile.mkdtemp(prefix=destination.name + ".tmp-", dir=destination.parent))
    try:
        document_lines = "\n".join(document.to_json() for document in documents) + "\n"
        chunk_lines = "\n".join(_canonical_json(chunk.to_dict()) for chunk in chunks) + "\n"
        _write_atomic(temp_dir / "documents.jsonl", document_lines)
        _write_atomic(temp_dir / "chunks.jsonl", chunk_lines)
        checksums = {
            "documents_sha256": hashlib.sha256(document_lines.encode("utf-8")).hexdigest(),
            "chunks_sha256": hashlib.sha256(chunk_lines.encode("utf-8")).hexdigest(),
        }
        source_summary: dict[str, int] = {}
        for document in documents:
            source_summary[document.source_type] = source_summary.get(document.source_type, 0) + 1
        manifest = {
            "schema_version": KNOWLEDGE_BASE_SCHEMA_VERSION,
            "contract_schema_version": CONTRACT_SCHEMA_VERSION,
            "knowledge_base_version": knowledge_base_version,
            "document_count": len(documents), "chunk_count": len(chunks),
            "checksums": checksums, "source_provenance_summary": source_summary,
            "document_ids": [document.document_id for document in documents],
            "chunk_ids": chunk_ids,
            "validation_status": "passed",
            "creation_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        }
        _write_atomic(temp_dir / "manifest.json", _canonical_json(manifest) + "\n")
        os.replace(temp_dir, destination)
        return manifest
    except Exception:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise
