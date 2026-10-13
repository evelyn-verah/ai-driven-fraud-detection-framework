import numpy as np
import pandas as pd

from src.risk_engine.final_architecture import (
    CALIBRATED_RF_ALERT_THRESHOLD,
    CALIBRATED_THRESHOLD_PROVENANCE,
    FINAL_ARCHITECTURE_VERSION,
    FinalRiskAssessment,
    FinalRiskAssessmentConfig,
)


class _Supervised:
    def predict_proba(self, frame):
        probability = np.clip(frame["amount"].to_numpy(dtype=float) / 100.0, 0.0, 1.0)
        return np.column_stack([1.0 - probability, probability])


class _Identity:
    def transform(self, frame):
        return frame.to_numpy(dtype=float)


class _Anomaly:
    def __init__(self, column_count):
        self.column_count = column_count

    def score_samples(self, values):
        assert values.shape[1] == self.column_count
        return -np.sum(values, axis=1)


class _BehavioralAnomaly(_Anomaly):
    def score_samples(self, values):
        assert values.shape[1] == self.column_count
        return -np.sum(values[:, 4:], axis=1)


def _models():
    return (
        _Supervised(),
        {"preprocessor": _Identity(), "model": _Anomaly(4)},
        {"preprocessor": _Identity(), "model": _BehavioralAnomaly(13)},
    )


def _frame(targets=(0, 1)):
    return pd.DataFrame(
        {
            "step": [1, 1],
            "type": ["TRANSFER", "CASH_OUT"],
            "amount": [10.0, 80.0],
            "oldbalanceOrg": [20.0, 100.0],
            "oldbalanceDest": [0.0, 5.0],
            "nameOrig": ["sender-a", "sender-b"],
            "nameDest": ["receiver-a", "receiver-b"],
            "isFraud": list(targets),
        },
        index=[11, 12],
    )


def test_version_and_threshold_provenance_are_frozen():
    config = FinalRiskAssessmentConfig()
    assert config.architecture_version == FINAL_ARCHITECTURE_VERSION
    assert config.fraud_alert_threshold == CALIBRATED_RF_ALERT_THRESHOLD
    assert "steps 46-200" in CALIBRATED_THRESHOLD_PROVENANCE


def test_rf_probability_drives_alert_and_ranking_consistency():
    assessment = FinalRiskAssessment(*_models())
    result = assessment.assess_step(_frame())
    assert list(result.index) == [11, 12]
    assert result.loc[11, "fraud_probability"] < result.loc[12, "fraud_probability"]
    assert not result.loc[11, "alert"]
    assert result.loc[12, "alert"]
    assert np.array_equal(result["alert"].to_numpy(), result["fraud_probability"].to_numpy() >= CALIBRATED_RF_ALERT_THRESHOLD)


def test_anomalies_and_rules_are_independent_context_not_fusion():
    assessment = FinalRiskAssessment(*_models())
    result = assessment.assess_step(_frame())
    assert "baseline_anomaly_intensity" in result
    assert "behavioral_anomaly_intensity" in result
    assert (result["baseline_anomaly_intensity"] >= 0).all()
    assert all("not a probability" in explanation for explanation in result["explanation"])
    assert result.loc[11, "triggered_rules"] == []

    altered = _frame().copy()
    altered.loc[11, "amount"] = 30.0
    altered.loc[11, "oldbalanceOrg"] = 10.0
    altered_result = FinalRiskAssessment(*_models()).assess_step(altered)
    assert "amount_exceeds_oldbalanceOrg" in altered_result.loc[11, "triggered_rules"]
    assert altered_result.loc[11, "fraud_probability"] < altered_result.loc[12, "fraud_probability"]


def test_target_changes_do_not_change_scores_and_repeated_runs_are_reproducible():
    first = FinalRiskAssessment(*_models()).assess_step(_frame((0, 1)))
    second = FinalRiskAssessment(*_models()).assess_step(_frame((1, 0)))
    pd.testing.assert_frame_equal(first, second)
    repeated = FinalRiskAssessment(*_models()).assess_step(_frame())
    pd.testing.assert_frame_equal(first, repeated)


def test_same_step_history_is_not_visible_to_behavioral_indicator():
    assessment = FinalRiskAssessment(*_models())
    first = assessment.assess_step(_frame())
    second_frame = _frame().assign(step=2, nameOrig=["sender-a", "sender-c"])
    second = assessment.assess_step(second_frame)
    assert first.loc[11, "behavioral_anomaly_intensity"] == first.loc[12, "behavioral_anomaly_intensity"]
    assert second.loc[11, "behavioral_anomaly_intensity"] != second.loc[12, "behavioral_anomaly_intensity"]
