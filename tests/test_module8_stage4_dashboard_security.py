from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from src.dashboard.feedback_store import initialize_database
from src.security.dashboard_access import (
    AuthorizationError,
    DashboardContext,
    analyst_safe_detail,
    authorized_detail,
    authorized_scores,
    issue_local_context,
    require_permission,
    safe_feedback_summary,
    submit_review,
)
from src.security.storage_security import sha256_file


def _scores() -> pd.DataFrame:
    return pd.DataFrame({
        "row_id": [0], "step": [378], "isFraud": [1], "isFlaggedFraud": [0],
        "nameOrig": ["C123"], "nameDest": ["M456"], "fraud_probability": [0.5],
        "baseline_anomaly_intensity": [0.1], "behavioral_anomaly_intensity": [0.2],
        "rule_score_context": [0.0], "alert": [True],
    })


def _detail() -> dict:
    return {
        "metadata": {"row_id": 0, "step": 378, "type": "TRANSFER", "amount": 10.0,
                     "oldbalanceOrg": 20.0, "newbalanceOrig": 10.0,
                     "oldbalanceDest": 0.0, "newbalanceDest": 10.0,
                     "isFraud": 1, "nameOrig": "C123", "nameDest": "M456"},
        "intelligence": {"context": {"fraud_probability": 0.5, "alert": True,
                                        "threshold": 0.3, "isFraud": 1},
                         "explanation": {"observed_facts": ["amount"], "notes": "private"},
                         "reviewer": "secret"},
        "reviewer_label": "secret", "notes": "private",
    }


def test_viewer_can_read_safe_scores_and_details_but_not_write(tmp_path: Path):
    viewer = issue_local_context("Viewer", trusted_local_identity=True)
    projected = authorized_scores(viewer, _scores())
    assert "isFraud" not in projected.columns and "nameOrig" not in projected.columns
    safe = authorized_detail(viewer, _detail())
    assert "isFraud" not in str(safe) and "nameOrig" not in str(safe)
    with pytest.raises(AuthorizationError, match="denied"):
        submit_review(viewer, str(tmp_path / "reviews.sqlite3"), 0, "Unreviewed", "a", None, trusted_root=str(tmp_path))


def test_analyst_can_submit_review_and_read_aggregate_only(tmp_path: Path):
    analyst = issue_local_context("Analyst", trusted_local_identity=True)
    db = tmp_path / "reviews.sqlite3"
    event = submit_review(analyst, str(db), 0, "Escalated", "analyst-one", "private note",
                          trusted_root=str(tmp_path))
    assert event.row_id == 0
    summary = safe_feedback_summary(analyst, str(db), trusted_root=str(tmp_path))
    assert summary == {"event_count": 1, "status_counts": {"Escalated": 1}}
    assert "analyst-one" not in str(summary) and "private note" not in str(summary)


def test_unknown_or_missing_context_denied():
    for context in (None, DashboardContext("Viewer", authenticated=True),
                    DashboardContext("Administrator", authenticated=True)):
        with pytest.raises(AuthorizationError):
            require_permission(context, "dashboard.read")
    with pytest.raises(AuthorizationError):
        issue_local_context("Owner", trusted_local_identity=True)
    with pytest.raises(AuthorizationError):
        issue_local_context("Administrator")


def test_privilege_escalation_and_feedback_access_denied(tmp_path: Path):
    viewer = issue_local_context("Viewer", trusted_local_identity=True)
    with pytest.raises(AuthorizationError):
        safe_feedback_summary(viewer, str(tmp_path / "missing.sqlite3"), trusted_root=str(tmp_path))
    with pytest.raises(AuthorizationError):
        submit_review(viewer, str(tmp_path / "reviews.sqlite3"), 0, "Unreviewed", "a", None, trusted_root=str(tmp_path))


def test_safe_detail_projection_drops_sensitive_fields():
    safe = analyst_safe_detail(_detail())
    text = str(safe)
    for value in ("isFraud", "nameOrig", "nameDest", "reviewer", "private"):
        assert value not in text
    assert safe["metadata"]["row_id"] == 0


def test_admin_has_diagnostics_but_no_sensitive_projection(tmp_path: Path):
    admin = issue_local_context("Administrator", trusted_local_identity=True)
    require_permission(admin, "diagnostics.read")
    with pytest.raises(AuthorizationError):
        submit_review(admin, str(tmp_path / "reviews.sqlite3"), 0, "Unreviewed", "a", None, trusted_root=str(tmp_path))


def test_frozen_artifact_hashes_unchanged():
    root = Path(__file__).resolve().parents[1]
    expected = {
        root / "artifacts/module4_final_holdout_recovery_v1/complete_holdout_scores.csv": "16ab136cab8313db935fb30a6f182ddd15db7de28c9d76bdfa089345a35f9410",
        root / "artifacts/module5_authoritative_v1/module5_v1_freeze_manifest.json": "cba41469946685007cf475c3bfe2661076b19ca028bc883d1920f724aaa6d83c",
        root / "artifacts/module6_v1_freeze_manifest.json": "3d286b4f2e5fceca079c294a0be54ff80ad6286c7e1c34bbd687da4c924006fc",
        root / "artifacts/module7_v1_freeze_manifest.json": "8a6ce8bb8cab6c0437ac3ad63744b907dbf4688957bbf4fcbbc88eec26b280c3",
    }
    for path, checksum in expected.items():
        assert sha256_file(path) == checksum

