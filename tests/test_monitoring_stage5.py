import json
import sqlite3
from pathlib import Path

import pandas as pd
import pytest

from src.dashboard.config import FROZEN_ARCHITECTURE_VERSION, FROZEN_THRESHOLD
from src.monitoring import lifecycle
from src.monitoring.contracts import MonitoringWindow


def _fixture(tmp_path, feedback=False):
    cache = tmp_path / "scores.csv"
    cache.write_text("fixture", encoding="utf-8")
    sidecar = tmp_path / "sidecar"
    sidecar.mkdir()
    frame = pd.DataFrame({
        "row_id": [0, 1, 2, 3], "step": [378, 378, 379, 379],
        "fraud_probability": [0.1, 0.5, 0.2, 0.8],
        "baseline_anomaly_intensity": [0.1, 0.2, 0.3, 0.4],
        "behavioral_anomaly_intensity": [0.2, 0.3, 0.4, 0.5],
        "rule_score_context": [0.0, 0.1, 0.0, 0.2],
        "alert": [False, True, False, True],
    })
    metadata = pd.DataFrame({"row_id": [0, 1, 2, 3], "step": [378, 378, 379, 379], "type": ["PAYMENT", "TRANSFER", "PAYMENT", "TRANSFER"], "amount": [1.0, 2.0, 3.0, 4.0]})
    source = {"score_cache_path": str(cache), "frozen_threshold": FROZEN_THRESHOLD, "complete_step_counts": {"378": 2, "379": 2}}
    feedback_db = tmp_path / "feedback.sqlite3"
    if feedback:
        with sqlite3.connect(feedback_db) as db:
            db.execute("CREATE TABLE review_events (event_id INTEGER, row_id INTEGER, status TEXT, reviewer_label TEXT, notes TEXT, created_at_utc TEXT)")
    config = lifecycle.MonitoringLifecycleConfig(
        "test_run", MonitoringWindow("ref", 378, 378, "reference", "fixed fixture"),
        MonitoringWindow("cmp", 379, 379, "comparison", "fixed fixture"),
        (MonitoringWindow("ref", 378, 378, "reference", "fixed fixture"), MonitoringWindow("cmp", 379, 379, "comparison", "fixed fixture")),
        tmp_path / "runs", cache, sidecar, feedback, feedback_db,
        FROZEN_ARCHITECTURE_VERSION, FROZEN_THRESHOLD,
    )
    return config, frame, metadata, source


def test_valid_and_invalid_configuration(tmp_path):
    config, *_ = _fixture(tmp_path)
    assert lifecycle.validate_config(config) is config
    with pytest.raises(ValueError, match="threshold"):
        lifecycle.validate_config(lifecycle.MonitoringLifecycleConfig(**{**config.__dict__, "frozen_threshold": 0.1}))


def test_overlapping_windows_rejected(tmp_path):
    config, *_ = _fixture(tmp_path)
    overlap = MonitoringWindow("bad", 378, 379, "bad", "fixture")
    bad = lifecycle.MonitoringLifecycleConfig(config.run_id, overlap, config.comparison_window, config.summary_windows, config.output_dir, config.score_cache_path, config.metadata_sidecar_path)
    with pytest.raises(ValueError, match="ordered"):
        lifecycle.validate_config(bad)


def test_successful_run_privacy_checksums_feedback_and_collision(tmp_path, monkeypatch):
    config, frame, metadata, source = _fixture(tmp_path, feedback=True)
    monkeypatch.setattr(lifecycle, "load_frozen_inputs", lambda include_metadata=True: (frame.copy(), metadata.copy(), source))
    manifest = lifecycle.run_monitoring(config)
    assert manifest["status"] == "completed"
    run_dir = config.output_dir / config.run_id
    assert manifest["output_checksums"]
    for name, checksum in manifest["output_checksums"].items():
        assert lifecycle.sha256_file(run_dir / f"{name}.json") == checksum
        text = (run_dir / f"{name}.json").read_text(encoding="utf-8")
        assert "isFraud" not in text and "reviewer_label" not in text and "notes" not in text
    assert json.loads((run_dir / "feedback.json").read_text())["event_count"] == 0
    with pytest.raises(FileExistsError):
        lifecycle.run_monitoring(config)


def test_feedback_can_be_disabled(tmp_path, monkeypatch):
    config, frame, metadata, source = _fixture(tmp_path)
    monkeypatch.setattr(lifecycle, "load_frozen_inputs", lambda include_metadata=True: (frame.copy(), metadata.copy(), source))
    manifest = lifecycle.run_monitoring(config)
    assert "feedback" not in manifest["output_paths"]


def test_partial_failure_records_manifest(tmp_path, monkeypatch):
    config, *_ = _fixture(tmp_path)
    monkeypatch.setattr(lifecycle, "load_frozen_inputs", lambda include_metadata=True: (_ for _ in ()).throw(RuntimeError("fixture failure")))
    with pytest.raises(RuntimeError, match="fixture failure"):
        lifecycle.run_monitoring(config)
    manifest = json.loads((config.output_dir / config.run_id / "manifest.json").read_text())
    assert manifest["status"] == "failed"


def test_missing_sources_rejected(tmp_path):
    config, *_ = _fixture(tmp_path)
    missing = lifecycle.MonitoringLifecycleConfig(**{**config.__dict__, "score_cache_path": tmp_path / "missing.csv"})
    with pytest.raises(FileNotFoundError, match="score cache"):
        lifecycle.validate_config(missing)
