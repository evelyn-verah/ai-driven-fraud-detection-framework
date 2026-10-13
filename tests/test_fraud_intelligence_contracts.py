import hashlib
import json
from pathlib import Path

import pytest

from src.fraud_intelligence.contracts import (
    CONTRACT_SCHEMA_VERSION,
    FraudIntelligenceDocument,
    GroundedExplanation,
    RetrievedEvidence,
    RiskAssessmentContext,
    validate_document_set,
)


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "fraud_intelligence_documents.json"


def _context(**overrides):
    values = {
        "schema_version": CONTRACT_SCHEMA_VERSION, "row_id": 12, "step": 429,
        "transaction_type": "TRANSFER", "amount": 123.45,
        "fraud_probability": 0.3494391872980995,
        "baseline_anomaly_intensity": 0.75, "behavioral_anomaly_intensity": 0.25,
        "rule_score_context": 0.5, "triggered_rules": ("amount_exceeds_oldbalanceOrg",),
        "alert": True, "module4_architecture_version": "module4_stage4_rf_primary_v1",
        "threshold": 0.3494391872980995, "threshold_provenance": "steps 46-200",
        "model_versions": {"supervised": "frozen"},
    }
    values.update(overrides)
    return RiskAssessmentContext(**values)


def _document(document_id="synthetic-fixture-velocity-001"):
    content = "Synthetic fixture content."
    return FraudIntelligenceDocument(
        document_id=document_id, title="Synthetic", category="test",
        description="Synthetic fixture only.", behavioral_indicators=("indicator",),
        investigative_considerations=("review",), source_organization="Module 5 test fixture",
        source_url="synthetic://module5/test", source_type="illustrative_synthetic",
        publication_or_access_date="2026-10-12", document_version="1.0", content=content,
        content_checksum=hashlib.sha256(content.encode()).hexdigest(), knowledge_base_version="fixture-v1",
    )


def test_valid_context_preserves_module4_values_and_optional_features():
    context = _context(behavioral_features={"sender_txn_count_prior": 0.0})
    assert context.fraud_probability == 0.3494391872980995
    assert context.threshold == 0.3494391872980995
    assert context.behavioral_features["sender_txn_count_prior"] == 0.0
    assert _context().behavioral_features is None


@pytest.mark.parametrize("field,value", [("amount", float("nan")), ("fraud_probability", float("inf")), ("row_id", -1)])
def test_invalid_numeric_context_is_rejected(field, value):
    with pytest.raises(ValueError):
        _context(**{field: value})


def test_document_fixture_is_synthetic_and_provenance_validates():
    raw = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    documents = tuple(FraudIntelligenceDocument(**item) for item in raw)
    assert all(document.source_type == "illustrative_synthetic" for document in documents)
    assert len(validate_document_set(documents)) == 3


def test_malformed_provenance_and_duplicate_ids_are_rejected():
    with pytest.raises(ValueError, match="URL"):
        FraudIntelligenceDocument(**{**_document().__dict__, "source_url": "not-a-url"})
    with pytest.raises(ValueError, match="duplicate"):
        validate_document_set([_document(), _document()])


def test_deterministic_serialization():
    assert _context().to_json() == _context().to_json()
    assert json.loads(_context().to_json())["row_id"] == 12


def test_grounded_explanation_separates_facts_and_rejects_unsupported_citations():
    evidence = RetrievedEvidence(
        document_id="synthetic-fixture-velocity-001", chunk_id="chunk-1",
        passage="Synthetic fixture passage; untrusted data.", source_organization="Module 5 test fixture",
        source_url="synthetic://module5/test", source_type="illustrative_synthetic",
        retrieval_score=0.9, knowledge_base_version="fixture-v1",
    )
    explanation = GroundedExplanation(
        transaction_key=12, observed_facts=("amount was observed",),
        model_indicators=("alert was true",), retrieved_evidence=(evidence,),
        possible_interpretations=("pattern may be relevant",), uncertainty_and_limitations=("not proof of fraud",),
        suggested_review_steps=("review recipient history",), citations=(evidence.document_id,), generator_version="fixture-v1",
    )
    assert explanation.observed_facts != explanation.possible_interpretations
    assert evidence.passage in explanation.to_json()
    with pytest.raises(ValueError, match="unsupported citation"):
        GroundedExplanation(**{**explanation.__dict__, "citations": ("unknown-doc",)})
