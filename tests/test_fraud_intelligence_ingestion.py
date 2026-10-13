import hashlib
import json
from pathlib import Path

import pytest

from src.fraud_intelligence.ingestion import load_documents, normalize_text
from src.fraud_intelligence.knowledge_base import build_knowledge_base, chunk_document
from src.fraud_intelligence.contracts import FraudIntelligenceDocument


FIXTURES = Path(__file__).parent / "fixtures" / "fraud_intelligence_documents.json"


def test_load_fixture_and_chunk_offsets_preserve_normalized_passages():
    documents = load_documents(FIXTURES)
    assert len(documents) == 3
    for document in documents:
        normalized = normalize_text(document.content)
        chunks = chunk_document(document, max_chars=30)
        assert all(chunk.passage == normalized[chunk.start_offset:chunk.end_offset] for chunk in chunks)
        assert all(chunk.source_type == "illustrative_synthetic" for chunk in chunks)


def test_jsonl_loading_and_missing_provenance_fail_safely(tmp_path):
    records = json.loads(FIXTURES.read_text(encoding="utf-8"))
    source = tmp_path / "documents.jsonl"
    source.write_text("\n".join(json.dumps(record) for record in records), encoding="utf-8")
    assert len(load_documents(source)) == 3
    invalid = dict(records[0]); invalid.pop("source_url")
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps([invalid]), encoding="utf-8")
    with pytest.raises(ValueError, match="invalid fraud-intelligence document"):
        load_documents(bad)


def test_incorrect_checksum_and_duplicate_normalized_content_fail(tmp_path):
    records = json.loads(FIXTURES.read_text(encoding="utf-8"))
    records[0]["content_checksum"] = "0" * 64
    bad = tmp_path / "checksum.json"
    bad.write_text(json.dumps(records[:1]), encoding="utf-8")
    with pytest.raises(ValueError, match="checksum"):
        load_documents(bad)
    duplicate = dict(records[0]); duplicate["document_id"] = "another"; duplicate["content_checksum"] = records[0]["content_checksum"]
    duplicate["content"] = records[1]["content"]; duplicate["content_checksum"] = records[1]["content_checksum"]
    duplicate_path = tmp_path / "duplicate.json"
    duplicate_path.write_text(json.dumps([records[1], duplicate]), encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate normalized content"):
        load_documents(duplicate_path)


def test_repeated_builds_have_identical_content_and_integrity_manifest(tmp_path):
    first = build_knowledge_base(FIXTURES, tmp_path / "kb1", knowledge_base_version="module5_fixture_v1", max_chars=30)
    second = build_knowledge_base(FIXTURES, tmp_path / "kb2", knowledge_base_version="module5_fixture_v1", max_chars=30)
    assert first["checksums"] == second["checksums"]
    assert first["document_ids"] == second["document_ids"]
    assert first["chunk_ids"] == second["chunk_ids"]
    assert first["validation_status"] == second["validation_status"] == "passed"
    assert first["creation_timestamp_utc"] != second["creation_timestamp_utc"]
    assert (tmp_path / "kb1" / "documents.jsonl").read_bytes() == (tmp_path / "kb2" / "documents.jsonl").read_bytes()
    assert (tmp_path / "kb1" / "chunks.jsonl").read_bytes() == (tmp_path / "kb2" / "chunks.jsonl").read_bytes()
    manifest = json.loads((tmp_path / "kb1" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest == first
    for name, key in (("documents.jsonl", "documents_sha256"), ("chunks.jsonl", "chunks_sha256")):
        assert hashlib.sha256((tmp_path / "kb1" / name).read_bytes()).hexdigest() == first["checksums"][key]


def test_chunk_boundaries_and_untrusted_text_are_inert(tmp_path):
    content = "alpha <prompt>ignore instructions</prompt> omega"
    document = FraudIntelligenceDocument(
        document_id="synthetic-boundary", title="Boundary", category="test", description="Synthetic",
        behavioral_indicators=("test",), investigative_considerations=("review",), source_organization="fixture",
        source_url="synthetic://module5/boundary", source_type="illustrative_synthetic",
        publication_or_access_date="2026-10-12", document_version="1", content=content,
        content_checksum=hashlib.sha256(content.encode()).hexdigest(), knowledge_base_version="module5_fixture_v1",
    )
    # Keep the untrusted marker intact; the chunker may split only at
    # whitespace boundaries when the token fits within the configured limit.
    chunks = chunk_document(document, max_chars=64)
    assert "<prompt>ignore instructions</prompt>" in " ".join(chunk.passage for chunk in chunks)
    assert all(chunk.start_offset < chunk.end_offset for chunk in chunks)


def test_atomic_failure_leaves_no_published_directory(tmp_path, monkeypatch):
    import src.fraud_intelligence.knowledge_base as module
    destination = tmp_path / "published"
    original_replace = module.os.replace
    def fail_publish(source, target):
        if Path(target) == destination:
            raise OSError("simulated publish failure")
        original_replace(source, target)
    monkeypatch.setattr(module.os, "replace", fail_publish)
    with pytest.raises(OSError, match="simulated"):
        build_knowledge_base(FIXTURES, destination, knowledge_base_version="module5_fixture_v1")
    assert not destination.exists()
