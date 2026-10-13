import pandas as pd
import pytest

from src.dashboard.data_access import DataValidationError, ScoreCache
from src.dashboard.details import build_transaction_details
from src.fraud_intelligence.knowledge_base import build_knowledge_base
from src.fraud_intelligence.retrieval import build_retrieval_index


def _cache() -> ScoreCache:
    return ScoreCache(frame=pd.DataFrame({
        "row_id": [0, 1], "step": [378, 379], "isFraud": [0, 1],
        "fraud_probability": [0.1, 0.9], "baseline_anomaly_intensity": [0.4, 0.5],
        "behavioral_anomaly_intensity": [0.4, 0.6], "rule_score_context": [0.0, 1.0],
        "alert": [False, True],
    }))


def _raw(path):
    pd.DataFrame([
        {"step": 378, "type": "TRANSFER", "amount": 2, "nameOrig": "sender-a", "oldbalanceOrg": 2, "newbalanceOrig": 0, "nameDest": "receiver-a", "oldbalanceDest": 0, "newbalanceDest": 2, "isFraud": 0, "isFlaggedFraud": 0},
        {"step": 379, "type": "CASH_OUT", "amount": 3, "nameOrig": "sender-b", "oldbalanceOrg": 3, "newbalanceOrig": 0, "nameDest": "receiver-b", "oldbalanceDest": 0, "newbalanceDest": 3, "isFraud": 1, "isFlaggedFraud": 0},
    ]).to_csv(path, index=False)


def test_real_context_preservation_and_grounded_evidence(tmp_path):
    raw = tmp_path / "raw.csv"
    _raw(raw)
    kb = tmp_path / "kb"
    build_knowledge_base("tests/fixtures/fraud_intelligence_documents.json", kb, knowledge_base_version="module5_fixture_v1")
    index = build_retrieval_index(kb, expected_version="module5_fixture_v1")
    details = build_transaction_details(1, _cache(), index, raw_path=str(raw))
    context = details.intelligence.context
    assert context.row_id == 1
    assert context.step == 379
    assert context.fraud_probability == 0.9
    assert context.alert is True
    assert context.triggered_rules == ()
    assert details.metadata["type"] == "CASH_OUT"
    assert "sender-b" not in details.intelligence.explanation.to_json()
    assert "receiver-b" not in details.intelligence.explanation.to_json()
    assert all(item.document_id in {e.document_id for e in details.intelligence.evidence} for item in details.intelligence.explanation.retrieved_evidence)


def test_invalid_selection_and_alignment_fail_safely(tmp_path):
    raw = tmp_path / "raw.csv"
    _raw(raw)
    kb = tmp_path / "kb"
    build_knowledge_base("tests/fixtures/fraud_intelligence_documents.json", kb, knowledge_base_version="module5_fixture_v1")
    index = build_retrieval_index(kb, expected_version="module5_fixture_v1")
    with pytest.raises(ValueError, match="outside"):
        build_transaction_details(2, _cache(), index, raw_path=str(raw))
    altered = tmp_path / "altered.csv"
    _raw(altered)
    frame = pd.read_csv(altered)
    frame.loc[1, "step"] = 378
    frame.to_csv(altered, index=False)
    with pytest.raises(DataValidationError, match="align"):
        build_transaction_details(1, _cache(), index, raw_path=str(altered))


def test_missing_raw_source_is_reported(tmp_path):
    kb = tmp_path / "kb"
    build_knowledge_base("tests/fixtures/fraud_intelligence_documents.json", kb, knowledge_base_version="module5_fixture_v1")
    index = build_retrieval_index(kb, expected_version="module5_fixture_v1")
    with pytest.raises(FileNotFoundError):
        build_transaction_details(0, _cache(), index, raw_path=str(tmp_path / "missing.csv"))
