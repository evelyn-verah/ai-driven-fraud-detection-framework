import hashlib
import json
from pathlib import Path

import pytest

from src.fraud_intelligence.contracts import CONTRACT_SCHEMA_VERSION, RiskAssessmentContext
from src.fraud_intelligence.knowledge_base import build_knowledge_base
from src.fraud_intelligence.retrieval import build_retrieval_index, build_transaction_query, evaluate_retrieval, normalize_query


FIXTURES = Path(__file__).parent / "fixtures"
DOCS = FIXTURES / "fraud_intelligence_documents.json"
EVAL = FIXTURES / "retrieval_evaluation.json"


def make_index(tmp_path):
    output = tmp_path / "kb"
    build_knowledge_base(DOCS, output, knowledge_base_version="module5_fixture_v1", max_chars=500)
    return output, build_retrieval_index(output, expected_version="module5_fixture_v1")


def test_deterministic_results_and_traceable_citations(tmp_path):
    _, index = make_index(tmp_path)
    first = index.search("rapid movement across recipients", top_k=3)
    second = index.search("rapid movement across recipients", top_k=3)
    assert first == second
    assert first[0].document_id == "synthetic-fixture-mule-002"
    assert first[0].source_url == "synthetic://module5/mule"
    assert first[0].passage
    assert first[0].knowledge_base_version == "module5_fixture_v1"


def test_filters_and_no_evidence(tmp_path):
    _, index = make_index(tmp_path)
    assert all(item.source_type == "illustrative_synthetic" for item in index.search("payment request", source_type="illustrative_synthetic"))
    assert index.search("payment request", category="mule_activity") == ()
    assert index.search("quantum spacecraft engine") == ()
    with pytest.raises(ValueError):
        index.search("x", source_type="unknown")
    with pytest.raises(ValueError):
        index.search(" ")
    with pytest.raises(ValueError):
        index.search("x", top_k=0)


def test_zero_score_ties_use_document_then_chunk_order(tmp_path):
    output, _ = make_index(tmp_path)
    index = build_retrieval_index(output, score_cutoff=0.0)
    results = index.search("unseen-token", top_k=3)
    assert [item.document_id for item in results] == sorted(item.document_id for item in results)


def test_manifest_and_chunk_tampering_are_rejected(tmp_path):
    output, _ = make_index(tmp_path)
    chunks = output / "chunks.jsonl"
    chunks.write_text(chunks.read_text(encoding="utf-8").replace("rapid movement", "tampered movement", 1), encoding="utf-8")
    with pytest.raises(ValueError, match="checksum"):
        build_retrieval_index(output)


def test_missing_provenance_and_version_are_rejected(tmp_path):
    output, _ = make_index(tmp_path)
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    manifest["source_provenance_summary"] = {}
    (output / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="checksum|provenance"):
        build_retrieval_index(output)


def test_query_builder_preserves_supplied_context_without_inventing_features():
    context = RiskAssessmentContext(
        schema_version=CONTRACT_SCHEMA_VERSION, row_id=4, step=10, transaction_type="TRANSFER", amount=12.5,
        fraud_probability=0.8, baseline_anomaly_intensity=0.0, behavioral_anomaly_intensity=0.6,
        rule_score_context=1.0, triggered_rules=("velocity_rule",), alert=True,
        module4_architecture_version="module4_stage4_rf_primary_v1", threshold=0.3494391872980995,
        threshold_provenance="steps_46_200", model_versions={"rf": "frozen"}, behavioral_features=None,
    )
    query = build_transaction_query(context)
    assert "TRANSFER" in query and "velocity_rule" in query and "behavioral_anomaly_indicator" in query
    assert "invented" not in query


def test_query_builder_does_not_change_module4_values():
    context = RiskAssessmentContext(
        schema_version=CONTRACT_SCHEMA_VERSION, row_id=1, step=1, transaction_type="CASH_OUT", amount=10.0,
        fraud_probability=0.7, baseline_anomaly_intensity=0.2, behavioral_anomaly_intensity=0.0,
        rule_score_context=0.0, triggered_rules=(), alert=True,
        module4_architecture_version="module4_stage4_rf_primary_v1", threshold=0.3494391872980995,
        threshold_provenance="steps_46_200", model_versions={"rf": "frozen"}, behavioral_features={"x": 1.25},
    )
    before = context.to_json()
    build_transaction_query(context)
    assert context.to_json() == before


def test_fixture_evaluation_is_explicitly_small_and_not_holdout_based(tmp_path):
    _, index = make_index(tmp_path)
    cases = json.loads(EVAL.read_text(encoding="utf-8"))
    metrics = evaluate_retrieval(index, cases, top_k=2)
    assert metrics["case_count"] == 5
    assert 0.0 <= metrics["recall_at_k"] <= 1.0
    assert metrics["no_evidence_rejection_accuracy"] == 1.0


def test_invalid_cutoff_and_expected_version_fail(tmp_path):
    output, _ = make_index(tmp_path)
    with pytest.raises(ValueError):
        build_retrieval_index(output, score_cutoff=2.0)
    with pytest.raises(ValueError, match="version"):
        build_retrieval_index(output, expected_version="other")


def test_domain_query_normalization_rejects_generic_and_expands_transfer_patterns(tmp_path):
    _, index = make_index(tmp_path)
    assert normalize_query("classical music orchestral composition analysis") == ""
    assert "money mule" in normalize_query("unusual incoming outgoing transfers counterparties sequence")
    assert index.search("classical music orchestral composition analysis") == ()


def test_domain_normalization_preserves_relevant_authoritative_results(tmp_path):
    output = tmp_path / "authoritative"
    build_knowledge_base(Path("data/fraud_intelligence/authoritative_documents.json"), output, knowledge_base_version="module5_authoritative_v1")
    index = build_retrieval_index(output, expected_version="module5_authoritative_v1")
    ids = [item.document_id for item in index.search("unusual incoming outgoing transfers counterparties sequence", top_k=3)]
    assert {"fbi-money-mule-awareness-2019", "fincen-imposter-mule-advisory-2020"}.issubset(ids)


def test_normalization_is_deterministic():
    query = "Unusual INCOMING counterparties sequence"
    assert normalize_query(query) == normalize_query(query)
