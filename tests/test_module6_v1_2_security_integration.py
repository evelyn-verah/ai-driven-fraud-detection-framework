from __future__ import annotations

from pathlib import Path
import subprocess
import sys

import pandas as pd
import pytest

from src.dashboard.data_access import ScoreCache
from src.dashboard.secure_app import SecureDashboard, create_secure_dashboard, main
from src.security.dashboard_access import AuthorizationError, issue_local_context
from src.security.storage_security import sha256_file


def _cache() -> ScoreCache:
    frame = pd.DataFrame({
        "row_id": pd.Series([0], dtype="int64"), "step": pd.Series([378], dtype="int16"),
        "isFraud": pd.Series([1], dtype="int8"), "fraud_probability": [0.5],
        "baseline_anomaly_intensity": [0.1], "behavioral_anomaly_intensity": [0.2],
        "rule_score_context": [0.0], "alert": [True],
    })
    return ScoreCache(frame=frame)


def test_secure_entry_point_denies_missing_or_forged_context(tmp_path: Path):
    with pytest.raises(AuthorizationError):
        main()
    with pytest.raises(AuthorizationError):
        create_secure_dashboard(type("Forged", (), {"role": "Administrator", "authenticated": True})(), trusted_root=tmp_path)


def test_supported_launcher_direct_execution_is_fail_closed():
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, "src/dashboard/app.py"], cwd=root,
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0
    assert "Traceback" not in result.stderr
    source = (root / "src/dashboard/app.py").read_text(encoding="utf-8")
    assert "streamlit_main" in source
    assert "save_review" not in source and "load_score_cache" not in source


def test_viewer_safe_reads_and_write_denial(tmp_path: Path):
    viewer = issue_local_context("Viewer", trusted_local_identity=True)
    dashboard = SecureDashboard(viewer, trusted_root=tmp_path, feedback_db=tmp_path / "reviews.sqlite3")
    projected = dashboard.load_scores(_write_score_cache(tmp_path))
    assert "isFraud" not in projected.columns
    with pytest.raises(AuthorizationError):
        dashboard.submit_review(0, "Unreviewed", "reviewer", "note")
    with pytest.raises(AuthorizationError):
        dashboard.feedback_summary()


def test_analyst_review_and_feedback_privacy(tmp_path: Path):
    analyst = issue_local_context("Analyst", trusted_local_identity=True)
    dashboard = SecureDashboard(analyst, trusted_root=tmp_path, feedback_db=tmp_path / "reviews.sqlite3")
    event = dashboard.submit_review(0, "Escalated", "reviewer", "sensitive note")
    assert event.row_id == 0
    summary = dashboard.feedback_summary()
    assert summary == {"event_count": 1, "status_counts": {"Escalated": 1}}
    assert "reviewer" not in str(summary) and "sensitive note" not in str(summary)


def test_administrator_diagnostics_are_safe(tmp_path: Path):
    admin = issue_local_context("Administrator", trusted_local_identity=True)
    dashboard = SecureDashboard(admin, trusted_root=tmp_path, feedback_db=tmp_path / "reviews.sqlite3")
    diagnostic = dashboard.diagnostics(_cache())
    assert set(diagnostic) == {"validation_status", "architecture_version", "threshold", "transaction_count", "alert_count", "source"}
    assert "isFraud" not in str(diagnostic)
    with pytest.raises(AuthorizationError):
        dashboard.submit_review(0, "Unreviewed", "reviewer")


def test_secure_entrypoint_checks_authorization_before_data_access(tmp_path: Path):
    viewer = issue_local_context("Viewer", trusted_local_identity=True)
    dashboard = SecureDashboard(viewer, trusted_root=tmp_path)
    # A missing source must not be observable through an unauthenticated path;
    # the missing context is rejected before filesystem access.
    with pytest.raises(AuthorizationError):
        SecureDashboard(None, trusted_root=tmp_path).load_scores(tmp_path / "missing.csv")
    assert dashboard.context is viewer


def test_historical_freeze_integrity():
    root = Path(__file__).resolve().parents[1]
    expected = {
        root / "artifacts/module4_final_holdout_recovery_v1/complete_holdout_scores.csv": "16ab136cab8313db935fb30a6f182ddd15db7de28c9d76bdfa089345a35f9410",
        root / "artifacts/module5_authoritative_v1/module5_v1_freeze_manifest.json": "cba41469946685007cf475c3bfe2661076b19ca028bc883d1920f724aaa6d83c",
        root / "artifacts/module6_v1_freeze_manifest.json": "3d286b4f2e5fceca079c294a0be54ff80ad6286c7e1c34bbd687da4c924006fc",
        root / "artifacts/module7_v1_freeze_manifest.json": "8a6ce8bb8cab6c0437ac3ad63744b907dbf4688957bbf4fcbbc88eec26b280c3",
    }
    for path, checksum in expected.items():
        assert sha256_file(path) == checksum


def _write_score_cache(tmp_path: Path) -> Path:
    path = tmp_path / "scores.csv"
    _cache().frame.to_csv(path, index=False)
    return path
