import numpy as np
import pandas as pd
import pytest
from sklearn.ensemble import IsolationForest
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from src.anomaly_detection.behavioral_features import add_behavioral_features
from src.risk_engine.behavioral_state import ChronologicalBehavioralProcessor
from src.risk_engine.contracts import validate_transactions
from src.risk_engine.decisions import RiskDecisionPolicy, make_risk_decisions
from src.risk_engine.fusion import FusionWeights, RiskScoreFusion
from src.risk_engine.normalization import EmpiricalCdfNormalizer
from src.risk_engine.rules import evaluate_paysim_rules
from src.risk_engine.scorers import (
    ANOMALY_BASE_FEATURES,
    SupervisedFraudScorer,
    IsolationForestScorer,
)


def sample_transactions():
    return pd.DataFrame(
        [
            {"step": 1, "type": "TRANSFER", "amount": 150.0, "oldbalanceOrg": 100.0, "oldbalanceDest": 0.0, "nameOrig": "A", "nameDest": "B"},
            {"step": 1, "type": "CASH_OUT", "amount": 50.0, "oldbalanceOrg": 50.0, "oldbalanceDest": 20.0, "nameOrig": "C", "nameDest": "B"},
            {"step": 2, "type": "TRANSFER", "amount": 300.0, "oldbalanceOrg": 300.0, "oldbalanceDest": 100.0, "nameOrig": "A", "nameDest": "B"},
        ]
    )


def test_streaming_processor_matches_existing_batch_features():
    frame = sample_transactions()
    expected = add_behavioral_features(frame)
    actual = ChronologicalBehavioralProcessor().transform_ordered(frame)
    pd.testing.assert_frame_equal(
        expected[expected.columns[-9:]],
        actual[expected.columns[-9:]],
        check_dtype=False,
    )


def test_streaming_processor_blocks_same_step_history():
    result = ChronologicalBehavioralProcessor().transform_ordered(sample_transactions())
    assert result.loc[0, "sender_txn_count_prior"] == 0
    assert result.loc[1, "sender_txn_count_prior"] == 0
    assert result.loc[2, "sender_txn_count_prior"] == 1


def test_processor_requires_complete_increasing_steps():
    frame = sample_transactions()
    processor = ChronologicalBehavioralProcessor()
    processor.process_step(frame.iloc[:2])
    with pytest.raises(ValueError, match="strictly increasing"):
        processor.process_step(frame.iloc[:1])


def test_contract_rejects_missing_and_invalid_data():
    with pytest.raises(ValueError, match="Missing PaySim"):
        validate_transactions(pd.DataFrame({"step": [1]}))
    frame = sample_transactions()
    frame.loc[0, "amount"] = -1
    with pytest.raises(ValueError, match="negative"):
        validate_transactions(frame)


def test_normalizer_is_development_fitted_and_bounded():
    normalizer = EmpiricalCdfNormalizer().fit(np.array([1.0, 2.0, 3.0]))
    assert np.all((normalizer.transform(np.array([0.0, 2.0, 4.0])) >= 0) & (normalizer.transform(np.array([0.0, 2.0, 4.0])) <= 1))
    with pytest.raises(RuntimeError):
        EmpiricalCdfNormalizer().transform(np.array([1.0]))


def test_fusion_is_deterministic_and_bounded():
    fusion = RiskScoreFusion(FusionWeights(supervised=2.0, anomaly_behavioral=1.0))
    first = fusion.combine(supervised=np.array([0.2, 0.8]), anomaly_behavioral=np.array([0.6, 0.4]))
    second = fusion.combine(supervised=np.array([0.2, 0.8]), anomaly_behavioral=np.array([0.6, 0.4]))
    assert np.array_equal(first, second)
    assert np.all((first >= 0) & (first <= 1))


def test_rules_and_explanations_have_provenance():
    frame = sample_transactions()
    behavioral = add_behavioral_features(frame)
    rules, reasons = evaluate_paysim_rules(frame, behavioral=behavioral)
    decisions = make_risk_decisions(
        np.array([0.9, 0.2, 0.6]),
        policy=RiskDecisionPolicy(),
        component_scores={"supervised": np.array([0.9, 0.2, 0.6])},
        rule_reasons=reasons,
    )
    assert np.all((rules >= 0) & (rules <= 1))
    assert decisions.loc[0, "alert"]
    assert "signal:supervised" in decisions.loc[0, "explanations"]
    assert "amount_exceeds_oldbalanceOrg" in decisions.loc[0, "explanations"]


def test_rule_and_decision_alignment_is_validated():
    frame = sample_transactions()
    with pytest.raises(ValueError, match="equal length"):
        evaluate_paysim_rules(frame, behavioral=pd.DataFrame())
    with pytest.raises(ValueError, match="align"):
        make_risk_decisions(np.array([0.5]), policy=RiskDecisionPolicy(), component_scores={"x": np.array([0.5, 0.5])})


def test_model_scoring_adapters_validate_and_bound_scores():
    frame = sample_transactions()

    class FakeSupervised:
        def predict_proba(self, values):
            assert list(values.columns) == ["step", "type", "amount", "oldbalanceOrg", "oldbalanceDest"]
            return np.column_stack([np.array([0.8, 0.6, 0.2]), np.array([0.2, 0.4, 0.8])])

    probabilities = SupervisedFraudScorer(FakeSupervised()).score(frame)
    assert np.array_equal(probabilities, np.array([0.2, 0.4, 0.8]))
    with pytest.raises(ValueError, match="Missing PaySim"):
        SupervisedFraudScorer(FakeSupervised()).score(frame.drop(columns=["type"]))

    numeric = frame[list(ANOMALY_BASE_FEATURES)]
    anomaly_model = Pipeline(
        [("scale", StandardScaler()), ("model", IsolationForest(n_estimators=5, random_state=42))]
    ).fit(numeric)
    anomaly_scores = IsolationForestScorer(anomaly_model, ANOMALY_BASE_FEATURES).score(frame)
    assert len(anomaly_scores) == len(frame)
    assert np.isfinite(anomaly_scores).all()
