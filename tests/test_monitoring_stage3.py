import json
import os
import pandas as pd
import pytest

from src.monitoring.contracts import MonitoringWindow
from src.monitoring.drift import analyze_drift, jensen_shannon, ks_statistic, psi

THRESHOLD = 0.3494391872980995

@pytest.fixture
def fixture_frames():
    ref = pd.DataFrame({"row_id": [0,1,2,3], "step": [378,378,378,378], "isFraud": [0,0,1,0], "fraud_probability": [.1,.2,.1,.2], "baseline_anomaly_intensity": [.2,.2,.2,.2], "behavioral_anomaly_intensity": [.3,.3,.3,.3], "rule_score_context": [0,0,0,0], "alert": [False,False,False,False]})
    cmp = pd.DataFrame({"row_id": [4,5,6,7], "step": [379,379,379,379], "isFraud": [0,1,0,1], "fraud_probability": [.8,.9,.8,.9], "baseline_anomaly_intensity": [.8,.8,.9,.9], "behavioral_anomaly_intensity": [.7,.7,.8,.8], "rule_score_context": [1,1,1,1], "alert": [True,True,True,True]})
    metadata = pd.DataFrame({"row_id": range(8), "step": [378]*4+[379]*4, "type": ["PAYMENT","PAYMENT","TRANSFER","TRANSFER","CASH_OUT","CASH_OUT","PAYMENT","PAYMENT"], "amount": [1.,1.,2.,2.,1000.,1000.,2000.,2000.], "isFraud": [0,0,1,0,0,1,0,1]})
    return pd.concat([ref, cmp], ignore_index=True), metadata

def windows():
    return (MonitoringWindow("reference",378,378,"reference", "predeclared first synthetic step"), MonitoringWindow("comparison",379,379,"comparison", "predeclared next synthetic step"))

def counts(): return {378: 4, 379: 4}

def test_identical_metric_helpers():
    values = [0., .2, .5, 1.]
    assert ks_statistic(values, values) == 0.0
    assert psi(values, values, [0,.5,1, float("inf")]) == pytest.approx(0.0)
    assert jensen_shannon(["a","b"], ["a","b"]) == pytest.approx(0.0)

def test_shifted_continuous_and_prediction_drift(fixture_frames):
    frame, md = fixture_frames; ref, cmp = windows()
    result = analyze_drift(frame, md, ref, cmp, counts())
    metric = result["data_drift"]["continuous"]["baseline_anomaly_intensity"]
    assert metric["ks_statistic"] > 0.9 and metric["psi"] > 0
    assert len(metric["reference_bin_proportions"]) == 10
    assert result["prediction_drift"]["fraud_probability"]["ks_statistic"] > 0.9
    assert result["prediction_drift"]["reference_alert_count"] == 0
    assert result["prediction_drift"]["comparison_alert_count"] == 4

def test_categorical_missing_levels_are_retained(fixture_frames):
    frame, md = fixture_frames; ref, cmp = windows(); result = analyze_drift(frame, md, ref, cmp, counts())
    metric = result["data_drift"]["categorical"]["type"]
    assert set(metric["reference_levels"]) == set(metric["comparison_levels"])
    assert metric["reference_levels"]["CASH_OUT"] == 0
    assert metric["comparison_levels"]["TRANSFER"] == 0
    assert metric["jensen_shannon_divergence"] > 0

def test_missing_values_constant_values_and_zero_bins(fixture_frames):
    frame, md = fixture_frames; frame.loc[0, "baseline_anomaly_intensity"] = float("nan"); md.loc[0, "amount"] = float("nan")
    ref, cmp = windows(); result = analyze_drift(frame, md, ref, cmp, counts())
    metric = result["data_drift"]["continuous"]["amount"]
    assert metric["reference_missingness"]["missing_count"] == 1
    assert metric["missingness_rate_change"] < 0
    assert psi([1,1,1], [1,1,1], [0,1,2]) == pytest.approx(0.0)

def test_invalid_window_order_and_overlap(fixture_frames):
    frame, md = fixture_frames; ref, cmp = windows()
    with pytest.raises(ValueError, match="precede"):
        analyze_drift(frame, md, cmp, ref, counts())
    overlap = MonitoringWindow("overlap", 378, 379, "x", "x")
    with pytest.raises(ValueError):
        analyze_drift(frame, md, ref, overlap, counts())

def test_partial_and_duplicate_or_misaligned_records_rejected(fixture_frames):
    frame, md = fixture_frames; ref, cmp = windows()
    with pytest.raises(ValueError, match="not complete"):
        analyze_drift(frame[frame.row_id != 0], md[md.row_id != 0], ref, cmp, counts())
    duplicate = frame.copy(); duplicate.loc[1, "row_id"] = 0
    with pytest.raises(ValueError, match="duplicate"):
        analyze_drift(duplicate, md, ref, cmp, counts())
    bad_md = md.copy(); bad_md.loc[0, "step"] = 999
    with pytest.raises(ValueError, match="alignment"):
        analyze_drift(frame, bad_md, ref, cmp, counts())

def test_deterministic_and_label_free_output(fixture_frames):
    frame, md = fixture_frames; ref, cmp = windows(); a = analyze_drift(frame, md, ref, cmp, counts()); b = analyze_drift(frame, md, ref, cmp, counts())
    a.pop("execution_timestamp_utc"); b.pop("execution_timestamp_utc"); assert a == b
    text = json.dumps(a, sort_keys=True)
    assert all(token not in text for token in ("isFraud", "nameOrig", "nameDest", "isFlaggedFraud"))

def test_empty_windows_require_authoritative_complete_counts(fixture_frames):
    frame, md = fixture_frames; ref, cmp = windows()
    with pytest.raises(ValueError, match="not complete"):
        analyze_drift(frame, md, ref, cmp, {378: 4, 379: 5})
