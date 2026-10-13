import json
import os
import pandas as pd
import pytest

from src.monitoring.contracts import MonitoringWindow, validate_windows
from src.monitoring.engine import summarize_monitoring, write_monitoring_result

THRESHOLD = 0.3494391872980995

@pytest.fixture
def fixture_frames():
    p = [0.1, 0.4, 0.8, 0.2, 0.35, 0.0]
    scores = pd.DataFrame({"row_id": range(6), "step": [378,378,379,380,380,381], "isFraud": [0,1,0,0,1,0], "fraud_probability": p, "baseline_anomaly_intensity": [0.1,0.2,0.9,0.3,0.4,0.5], "behavioral_anomaly_intensity": [0.2,0.3,0.8,0.1,0.5,0.6], "rule_score_context": [0,1,0,0,1,0], "alert": [x >= THRESHOLD for x in p]})
    metadata = pd.DataFrame({"row_id": range(6), "step": scores.step, "type": ["PAYMENT","TRANSFER","CASH_OUT","TRANSFER","PAYMENT","CASH_IN"], "amount": [10.,20.,30.,40.,50.,60.], "isFraud": scores.isFraud})
    return scores, metadata

def window(): return MonitoringWindow("w1", 378, 381, "test", "fixed synthetic complete steps")
def counts(): return {378: 2, 379: 1, 380: 2, 381: 1}

def test_counts_rates_and_types(fixture_frames):
    scores, md = fixture_frames; out = summarize_monitoring(scores, md, [window()], expected_step_counts=counts())
    assert out["summary"]["transaction_count"] == 6
    assert out["summary"]["alert_count"] == 3
    assert out["summary"]["alert_rate"] == 0.5
    assert out["summary"]["transaction_types"][0]["type"] == "CASH_IN"
    assert out["window_summaries"][0]["summary"]["amount"]["mean"] == 35.0

def test_probability_anomaly_bins_and_threshold(fixture_frames):
    out = summarize_monitoring(*fixture_frames, windows=[window()], expected_step_counts=counts())
    assert len(out["summary"]["fraud_probability"]["bins"]) == 10
    assert out["summary"]["fraud_probability"]["above_frozen_threshold_count"] == 3
    assert "not a fraud probability" in out["summary"]["anomaly"]["baseline_anomaly_intensity"]["interpretation"]

def test_validation_rejects_duplicates_and_bad_windows(fixture_frames):
    scores, md = fixture_frames; bad = scores.copy(); bad.loc[1, "row_id"] = 0
    with pytest.raises(ValueError): summarize_monitoring(bad, md, [window()], expected_step_counts=counts())
    with pytest.raises(ValueError): validate_windows([MonitoringWindow("a",378,379,"x","x"), MonitoringWindow("b",379,380,"x","x")])
    with pytest.raises(ValueError): summarize_monitoring(scores, md, [MonitoringWindow("bad",377,381,"x","x")], expected_step_counts=counts())

def test_alignment_and_required_fields(fixture_frames):
    scores, md = fixture_frames; md = md.copy(); md.loc[0, "step"] = 999
    with pytest.raises(ValueError): summarize_monitoring(scores, md, [window()], expected_step_counts=counts())
    with pytest.raises(ValueError): summarize_monitoring(scores.drop(columns=["alert"]), None, [window()], expected_step_counts=counts())

def test_outputs_exclude_internal_labels_and_are_reproducible(fixture_frames, tmp_path):
    scores, md = fixture_frames; a = summarize_monitoring(scores, md, [window()], expected_step_counts=counts()); b = summarize_monitoring(scores, md, [window()], expected_step_counts=counts())
    a.pop("execution_timestamp_utc"); b.pop("execution_timestamp_utc"); assert a == b
    path = write_monitoring_result(a, tmp_path / "result.json")
    text = path.read_text(encoding="utf-8")
    assert all(token not in text for token in ("isFraud", "nameOrig", "nameDest", "isFlaggedFraud", "analyst notes"))
    assert json.loads(text)["schema_version"].startswith("module7_stage2")

def test_atomic_write_failure_leaves_no_partial(monkeypatch, tmp_path, fixture_frames):
    scores, md = fixture_frames; result = summarize_monitoring(scores, md, [window()], expected_step_counts=counts()); destination = tmp_path / "result.json"
    def fail(*args): raise OSError("simulated replace failure")
    monkeypatch.setattr(os, "replace", fail)
    with pytest.raises(OSError): write_monitoring_result(result, destination)
    assert not destination.exists() and not list(tmp_path.glob("*.tmp"))

def test_partial_step_is_rejected_as_complete_window(fixture_frames):
    scores, md = fixture_frames
    partial = scores[scores.row_id != 1]
    with pytest.raises(ValueError, match="not complete"):
        summarize_monitoring(partial, md[md.row_id != 1], [MonitoringWindow("partial", 378, 378, "test", "partial fixture")], expected_step_counts={378: 2})

def test_missing_step_and_missing_expected_counts_are_rejected(fixture_frames):
    scores, md = fixture_frames
    with pytest.raises(ValueError, match="without authoritative counts"):
        summarize_monitoring(scores, md, [MonitoringWindow("missing", 378, 382, "test", "missing step")], expected_step_counts=counts())
    with pytest.raises(ValueError, match="expected_step_counts"):
        summarize_monitoring(scores, md, [window()])
