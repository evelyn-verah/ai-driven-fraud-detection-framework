import json
from pathlib import Path

from src.fraud_intelligence.knowledge_base import build_knowledge_base
from src.fraud_intelligence.retrieval import build_retrieval_index


ROOT = Path(__file__).parents[1]
DOCUMENTS = ROOT / "data/fraud_intelligence/authoritative_documents.json"
REVIEW = ROOT / "data/fraud_intelligence/authoritative_source_review_manifest.json"


def test_authoritative_manifest_has_verified_locators_and_date_types():
    documents = json.loads(DOCUMENTS.read_text(encoding="utf-8"))
    review = json.loads(REVIEW.read_text(encoding="utf-8"))
    assert len(documents) == 10
    assert len(review["documents"]) == len(documents)
    assert {record["source_type"] for record in documents} == {"authoritative"}
    assert all(record["knowledge_base_version"] == "module5_authoritative_v1" for record in documents)
    assert all(item["source_locator"] and item["date_type"] in {"publication", "access"} for item in review["documents"])
    assert {item["date_type"] for item in review["documents"]} == {"publication", "access"}


def test_authoritative_build_is_deterministic_and_retrievable(tmp_path):
    first = build_knowledge_base(DOCUMENTS, tmp_path / "first", knowledge_base_version="module5_authoritative_v1")
    second = build_knowledge_base(DOCUMENTS, tmp_path / "second", knowledge_base_version="module5_authoritative_v1")
    assert first["checksums"] == second["checksums"]
    index = build_retrieval_index(tmp_path / "first", expected_version="module5_authoritative_v1")
    results = index.search("phishing credential malicious link", top_k=2)
    assert results
    assert all(item.source_type == "authoritative" for item in results)
    assert all(item.document_id and item.chunk_id and item.source_url and item.passage for item in results)

