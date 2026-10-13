import json

import numpy as np
import pandas as pd
import pytest

from src.risk_engine.behavioral_state import iter_complete_steps
from src.risk_engine.development_pipeline import (
    DevelopmentSplit,
    apply_calibration,
    calibrate_fusion,
    fit_calibration_normalizers,
    fit_fusion_weights,
    load_score_cache,
    score_development_to_csv,
)
from src.risk_engine.fusion import FusionWeights


class FakeSupervised:
    def predict_proba(self, frame):
        values = np.clip(frame["amount"].to_numpy(dtype=float) / 100.0, 0.01, 0.99)
        return np.column_stack([1.0 - values, values])


class FakePreprocessor:
    def transform(self, frame):
        return frame.to_numpy(dtype=float)


class FakeAnomaly:
    def score_samples(self, values):
        return -np.sum(values, axis=1)


def _rows():
    rows = []
    for step in range(1, 4):
        for offset in range(3):
            rows.append(
                {
                    "step": step,
                    "type": "TRANSFER",
                    "amount": float(10 + step * 10 + offset),
                    "oldbalanceOrg": 100.0,
                    "oldbalanceDest": 20.0,
                    "nameOrig": f"sender-{offset}",
                    "nameDest": f"receiver-{offset}",
                    "isFraud": int(step == 3 and offset == 2),
                }
            )
    return pd.DataFrame(rows)


def _models():
    anomaly = {"preprocessor": FakePreprocessor(), "model": FakeAnomaly()}
    return FakeSupervised(), anomaly, anomaly


def test_chunk_boundary_yields_complete_steps(tmp_path):
    source = tmp_path / "transactions.csv"
    _rows().to_csv(source, index=False)
    frames = list(iter_complete_steps(str(source), chunksize=4, include_target=True))
    assert [int(frame["step"].iloc[0]) for frame in frames] == [1, 2, 3]
    assert [len(frame) for frame in frames] == [3, 3, 3]
    assert all(frame["step"].nunique() == 1 for frame in frames)


def test_score_cache_is_aligned_and_reproducible(tmp_path):
    source = tmp_path / "transactions.csv"
    _rows().to_csv(source, index=False)
    split = DevelopmentSplit(calibration_start=2, calibration_end=2, evaluation_start=3, evaluation_end=3)
    models = _models()
    first_path = tmp_path / "first.csv"
    second_path = tmp_path / "second.csv"
    first = score_development_to_csv(source, first_path, supervised_model=models[0], baseline_model=models[1], behavioral_model=models[2], chunksize=4, split=split)
    second = score_development_to_csv(source, second_path, supervised_model=models[0], baseline_model=models[1], behavioral_model=models[2], chunksize=5, split=split)
    assert first["rows_written"] == second["rows_written"] == 6
    pd.testing.assert_frame_equal(load_score_cache(first_path), load_score_cache(second_path))


def test_calibration_fits_only_on_calibration_rows_and_applies_frozen_scores():
    cache = pd.DataFrame(
        {
            "row_id": [0, 1, 2, 3],
            "step": [2, 2, 3, 3],
            "isFraud": [0, 1, 0, 1],
            "supervised_score": [0.1, 0.8, 0.2, 0.7],
            "anomaly_baseline_raw": [1.0, 2.0, 100.0, 200.0],
            "anomaly_behavioral_raw": [2.0, 3.0, 300.0, 400.0],
            "rule_score": [0.0, 1.0, 0.0, 1.0],
            "rule_reasons_json": ["[]", '["rule"]', "[]", '["rule"]'],
        }
    )
    split = DevelopmentSplit(calibration_start=2, calibration_end=2, evaluation_start=3, evaluation_end=3)
    calibration = calibrate_fusion(cache.iloc[:2], weights=FusionWeights(supervised=1.0, anomaly_behavioral=1.0, rules=1.0), split=split)
    normalizers = fit_calibration_normalizers(cache.iloc[:2], split=split)
    decisions = apply_calibration(cache.iloc[2:], calibration, normalizers=normalizers)
    assert len(decisions) == 2
    assert decisions["risk_score"].between(0, 1).all()
    assert all(isinstance(value, list) and value for value in decisions["explanations"])
    assert np.array_equal(normalizers[0].transform(np.array([100.0])), np.array([1.0]))


def test_calibration_rejects_evaluation_rows():
    cache = pd.DataFrame(
        {
            "row_id": [0], "step": [3], "isFraud": [0],
            "supervised_score": [0.1], "anomaly_baseline_raw": [1.0],
            "anomaly_behavioral_raw": [1.0], "rule_score": [0.0],
            "rule_reasons_json": [json.dumps([])],
        }
    )
    split = DevelopmentSplit(calibration_start=2, calibration_end=2, evaluation_start=3, evaluation_end=3)
    try:
        calibrate_fusion(cache, weights=FusionWeights(), split=split)
    except ValueError as error:
        assert "outside calibration" in str(error)
    else:
        raise AssertionError("evaluation rows must not be accepted for calibration")


def test_fusion_weight_search_is_calibration_only():
    cache = pd.DataFrame(
        {
            "row_id": [0, 1], "step": [2, 2], "isFraud": [0, 1],
            "supervised_score": [0.1, 0.9], "anomaly_baseline_raw": [1.0, 2.0],
            "anomaly_behavioral_raw": [1.0, 2.0], "rule_score": [0.0, 1.0],
            "rule_reasons_json": ["[]", '["rule"]'],
        }
    )
    split = DevelopmentSplit(calibration_start=2, calibration_end=2, evaluation_start=3, evaluation_end=3)
    selected = fit_fusion_weights(cache, candidates=(FusionWeights(supervised=1.0),), split=split)
    assert selected == FusionWeights(supervised=1.0)


@pytest.mark.parametrize("fit", [fit_calibration_normalizers, fit_fusion_weights])
@pytest.mark.parametrize("step", [45, 201, 378])
def test_public_fit_helpers_reject_noncalibration_steps(fit, step):
    cache = pd.DataFrame({
        "row_id": [0, 1], "step": [step, step], "isFraud": [0, 1],
        "supervised_score": [0.1, 0.9], "anomaly_baseline_raw": [1.0, 2.0],
        "anomaly_behavioral_raw": [1.0, 2.0], "rule_score": [0.0, 1.0],
        "rule_reasons_json": ["[]", "[]"],
    })
    with pytest.raises(ValueError, match="outside calibration"):
        fit(cache)


@pytest.mark.parametrize("label_mode", ["mixed", "none", "all"])
def test_threshold_scan_matches_exhaustive_search(label_mode):
    from src.risk_engine.development_pipeline import _best_f1_threshold

    rng = np.random.default_rng(42)
    for size in [1, 7, 100]:
        scores = rng.integers(0, 11, size=size) / 10.0
        labels = rng.integers(0, 2, size=size)
        if label_mode != "mixed":
            labels[:] = int(label_mode == "all")
        expected = (0.0, 0.0)
        for threshold in np.unique(np.concatenate(([0.0, 1.0], scores))):
            predicted = scores >= threshold
            tp = int((predicted & (labels == 1)).sum())
            fp = int((predicted & (labels == 0)).sum())
            fn = int((~predicted & (labels == 1)).sum())
            denominator = 2 * tp + fp + fn
            f1 = 2 * tp / denominator if denominator else 0.0
            if f1 > expected[1]:
                expected = (float(threshold), f1)
        assert _best_f1_threshold(scores, labels) == expected
