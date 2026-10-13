import hashlib

import numpy as np
import pandas as pd
import pytest

from src.risk_engine.final_architecture import FinalRiskAssessment
from src.risk_engine.behavioral_state import ChronologicalBehavioralProcessor
from src.risk_engine.behavioral_state_reference import ReferenceChronologicalBehavioralProcessor
from src.risk_engine.holdout_recovery import (
    calculate_metrics,
    initialize_recovery,
    verify_prefix_cache,
    verify_real_model_boundary,
    compare_persisted_scores,
)


class _Supervised:
    def predict_proba(self, frame):
        p = np.clip(frame["amount"].to_numpy(dtype=float) / 100.0, 0.0, 1.0)
        return np.column_stack([1.0 - p, p])


class _Identity:
    def transform(self, frame):
        return frame.to_numpy(dtype=float)


class _Anomaly:
    def __init__(self, columns, behavioral=False):
        self.columns = columns
        self.behavioral = behavioral

    def score_samples(self, values):
        assert values.shape[1] == self.columns
        return -np.sum(values[:, 4:] if self.behavioral else values, axis=1)


def _models():
    return (
        _Supervised(),
        {"preprocessor": _Identity(), "model": _Anomaly(4)},
        {"preprocessor": _Identity(), "model": _Anomaly(13, behavioral=True)},
    )


def _row(step, sender, amount, fraud=0):
    return {
        "step": step, "type": "TRANSFER", "amount": float(amount),
        "oldbalanceOrg": 100.0, "oldbalanceDest": 20.0,
        "nameOrig": sender, "nameDest": "receiver", "isFraud": fraud,
    }


def test_boundary_reconstruction_matches_independent_reference():
    step_428 = pd.DataFrame([_row(428, "a", 10), _row(428, "b", 20)])
    step_429 = pd.DataFrame([_row(429, "a", 30), _row(429, "c", 40)])

    resumed = FinalRiskAssessment(*_models())
    resumed.process_history_step(step_428)
    resumed_scores = resumed.assess_step(step_429)

    reference = FinalRiskAssessment(*_models())
    reference.assess_step(step_428)
    reference_scores = reference.assess_step(step_429)

    pd.testing.assert_frame_equal(resumed_scores, reference_scores)


def test_prefix_verification_checks_raw_order_labels_and_step_completeness(tmp_path):
    rows = [_row(step, f"sender-{step}", step - 370, int(step == 428)) for step in range(378, 429)]
    raw = tmp_path / "raw.csv"
    pd.DataFrame(rows).to_csv(raw, index=False)
    prefix = tmp_path / "prefix.csv"
    pd.DataFrame(
        {
            "row_id": np.arange(len(rows)),
            "step": [row["step"] for row in rows],
            "isFraud": [row["isFraud"] for row in rows],
            "fraud_probability": np.full(len(rows), 0.1),
            "baseline_anomaly_intensity": np.full(len(rows), 0.2),
            "behavioral_anomaly_intensity": np.full(len(rows), 0.3),
            "rule_score_context": np.zeros(len(rows)),
            "alert": np.zeros(len(rows), dtype=bool),
        }
    ).to_csv(prefix, index=False)
    before = hashlib.sha256(prefix.read_bytes()).hexdigest()
    manifest = verify_prefix_cache(raw, prefix)
    assert manifest == {"prefix_rows": 51, "first_step": 378, "last_step": 428, "raw_alignment": True}
    assert hashlib.sha256(prefix.read_bytes()).hexdigest() == before


def test_initialize_recovery_is_versioned_and_non_destructive(tmp_path):
    prefix = tmp_path / "prefix.csv"
    prefix.write_text("row_id,step,isFraud,fraud_probability,baseline_anomaly_intensity,behavioral_anomaly_intensity,rule_score_context,alert\n0,378,0,0.1,0.2,0.3,0.0,False\n")
    recovery = tmp_path / "recovery"
    manifest = initialize_recovery(
        recovery,
        prefix,
        frozen_manifest={"architecture_version": "test"},
        prefix_manifest={"prefix_rows": 1, "first_step": 378, "last_step": 428, "raw_alignment": True},
    )
    assert manifest["last_completed_step"] == 428
    assert (recovery / "preserved_prefix_scores.csv").read_bytes() == prefix.read_bytes()
    assert (recovery / "recovery_manifest.json").exists()


def test_metrics_are_thresholded_only_after_score_frame_is_provided():
    frame = pd.DataFrame({"isFraud": [0, 1, 1], "fraud_probability": [0.1, 0.4, 0.8]})
    metrics = calculate_metrics(frame, threshold=0.35)
    assert metrics["rows"] == 3
    assert metrics["true_positives"] == 2
    assert metrics["false_positives"] == 0


def test_real_boundary_verifier_reconstructs_once_and_samples(monkeypatch, tmp_path):
    frames = [pd.DataFrame([_row(step, f"sender-{step}", 10.0)]) for step in range(378, 430)]
    calls = {"iterations": 0}

    def fake_iter(*args, **kwargs):
        calls["iterations"] += 1
        yield from frames

    monkeypatch.setattr("src.risk_engine.holdout_recovery.iter_complete_steps", fake_iter)
    monkeypatch.setattr(
        FinalRiskAssessment,
        "from_joblib_paths",
        classmethod(lambda cls, **kwargs: cls(*_models())),
    )
    result = verify_real_model_boundary(
        tmp_path / "raw.csv",
        model_paths={"supervised": tmp_path / "a", "baseline_anomaly": tmp_path / "b", "behavioral_anomaly": tmp_path / "c"},
        sample_size=1,
    )
    assert calls["iterations"] == 1
    assert result["history_steps_reconstructed"] == 51
    assert result["sample_rows"] == 1
    assert result["independent_replay"] is False


def test_optimized_behavioral_features_match_reference_across_boundaries_and_missing_history():
    rows = [
        _row(1, "sender-a", 10),
        _row(1, "sender-a", 20),
        {**_row(1, "sender-b", 30), "type": "CASH_OUT"},
        _row(2, "sender-a", 40),
        {**_row(2, "sender-c", 50), "type": "PAYMENT"},
        _row(3, "sender-b", 60),
    ]
    frame = pd.DataFrame(rows)
    optimized = ChronologicalBehavioralProcessor().transform_ordered(frame)
    reference = ReferenceChronologicalBehavioralProcessor().transform_ordered(frame)
    feature_columns = [
        "sender_txn_count_prior", "sender_velocity_3_steps_prior",
        "sender_avg_amount_prior", "sender_amount_ratio_to_avg_prior",
        "sender_same_type_count_prior", "sender_same_type_share_prior",
        "receiver_txn_count_prior", "receiver_avg_amount_prior",
        "receiver_amount_ratio_to_avg_prior",
    ]
    pd.testing.assert_frame_equal(
        optimized[feature_columns].reset_index(drop=True),
        reference[feature_columns].reset_index(drop=True),
        check_exact=True,
    )


def test_state_only_reconstruction_matches_every_internal_state_and_next_features():
    rows = [
        _row(1, "sender-a", 10), _row(1, "sender-a", 20),
        {**_row(1, "sender-b", 30), "type": "CASH_OUT"},
        _row(2, "sender-a", 40), {**_row(2, "sender-c", 50), "type": "PAYMENT"},
        _row(3, "sender-b", 60), _row(4, "sender-d", 70),
        _row(5, "sender-a", 80),
    ]
    frames = [group for _, group in pd.DataFrame(rows).groupby("step", sort=True, observed=True)]
    state_only = ChronologicalBehavioralProcessor()
    reference = ReferenceChronologicalBehavioralProcessor()
    state_names = (
        "_sender_count", "_sender_amount_sum", "_sender_type_count",
        "_receiver_count", "_receiver_amount_sum", "_sender_velocity",
        "_velocity_history", "_last_step",
    )
    for frame in frames[:-1]:
        state_only.process_state_only(frame)
        reference.process_step(frame)
        for name in state_names:
            left, right = getattr(state_only, name), getattr(reference, name)
            if name == "_velocity_history":
                assert list(left) == list(right)
            else:
                assert left == right
                if isinstance(left, dict):
                    assert {key: type(value) for key, value in left.items()} == {key: type(value) for key, value in right.items()}
    optimized_next = state_only.process_step(frames[-1])
    reference_next = reference.process_step(frames[-1])
    feature_columns = [
        "sender_txn_count_prior", "sender_velocity_3_steps_prior",
        "sender_avg_amount_prior", "sender_amount_ratio_to_avg_prior",
        "sender_same_type_count_prior", "sender_same_type_share_prior",
        "receiver_txn_count_prior", "receiver_avg_amount_prior",
        "receiver_amount_ratio_to_avg_prior",
    ]
    pd.testing.assert_frame_equal(optimized_next[feature_columns], reference_next[feature_columns], check_exact=True)


def test_persisted_score_tolerance_allows_serialization_noise_but_rejects_material_changes():
    regenerated = pd.DataFrame({
        "step": [428], "isFraud": [0], "fraud_probability": [0.3],
        "baseline_anomaly_intensity": [0.4], "behavioral_anomaly_intensity": [0.5],
        "rule_score_context": [0.0], "alert": [False],
    })
    persisted = regenerated.copy()
    persisted.loc[0, "fraud_probability"] += 5e-13
    differences = compare_persisted_scores(regenerated, persisted, expected_steps=np.array([428]), expected_labels=np.array([0]))
    assert differences["fraud_probability"] == pytest.approx(5e-13)
    persisted.loc[0, "fraud_probability"] += 2e-12
    with pytest.raises(ValueError, match="exceeds tolerance"):
        compare_persisted_scores(regenerated, persisted, expected_steps=np.array([428]), expected_labels=np.array([0]))
    persisted = regenerated.copy(); persisted.loc[0, "step"] = 427
    with pytest.raises(ValueError, match="misaligned"):
        compare_persisted_scores(regenerated, persisted, expected_steps=np.array([428]), expected_labels=np.array([0]))
    persisted = regenerated.copy(); persisted.loc[0, "alert"] = True
    with pytest.raises(ValueError, match="alert decisions"):
        compare_persisted_scores(regenerated, persisted, expected_steps=np.array([428]), expected_labels=np.array([0]))
