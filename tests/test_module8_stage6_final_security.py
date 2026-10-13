from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

from src.dashboard.secure_app import SecureDashboard
from src.security.dashboard_access import AuthorizationError, authorized_detail, issue_local_context
from src.security.input_validation import InputSecurityError, validate_paysim_frame
from src.security.storage_security import ArtifactIntegrityError, StorageSecurityError, safe_load_joblib, secure_read_sqlite, secure_save_review


ROOT = Path(__file__).resolve().parents[1]


def test_supported_launcher_fails_closed_without_identity():
    result = subprocess.run([sys.executable, "src/dashboard/app.py"], cwd=ROOT, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0
    assert "Traceback" not in result.stderr
    source = (ROOT / "src/dashboard/app.py").read_text(encoding="utf-8")
    assert "streamlit_main" in source and "load_score_cache" not in source


def test_dashboard_operations_require_real_context(tmp_path: Path):
    dashboard = SecureDashboard(None, trusted_root=tmp_path, feedback_db=tmp_path / "reviews.sqlite3")
    with pytest.raises(AuthorizationError):
        dashboard.load_scores(tmp_path / "scores.csv")
    with pytest.raises(AuthorizationError):
        dashboard.feedback_summary()
    with pytest.raises(AuthorizationError):
        dashboard.submit_review(0, "Unreviewed", "reviewer")
    with pytest.raises(AuthorizationError):
        SecureDashboard(type("Forged", (), {"role": "Administrator", "authenticated": True})(), trusted_root=tmp_path).feedback_summary()


def test_sensitive_projection_and_feedback_privacy(tmp_path: Path):
    viewer = issue_local_context("Viewer", trusted_local_identity=True)
    safe = authorized_detail(viewer, {"metadata": {"row_id": 1, "amount": 2.0, "isFraud": 1, "nameOrig": "sender", "nameDest": "receiver"}, "intelligence": {"context": {"alert": True}, "explanation": {"observed_facts": ["amount"], "notes": "secret"}}, "reviewer_label": "identity", "notes": "secret"})
    text = str(safe)
    assert all(value not in text for value in ("isFraud", "sender", "receiver", "identity", "secret"))
    db = tmp_path / "reviews.sqlite3"
    secure_save_review(db, 1, "Escalated", "reviewer", "private", trusted_root=tmp_path)
    with pytest.raises(StorageSecurityError):
        secure_read_sqlite(db, trusted_root=tmp_path, production_only=True, demonstration_path=db)


def test_input_and_sqlite_adversarial_fixtures(tmp_path: Path):
    frame = pd.DataFrame({"step": [378], "type": ["PAYMENT"], "amount": [float("nan")], "oldbalanceOrg": [1.0], "newbalanceOrig": [0.0], "oldbalanceDest": [0.0], "newbalanceDest": [1.0]})
    with pytest.raises(InputSecurityError):
        validate_paysim_frame(frame)
    malformed = tmp_path / "bad.sqlite3"
    malformed.write_bytes(b"not sqlite")
    with pytest.raises(StorageSecurityError):
        secure_read_sqlite(malformed, trusted_root=tmp_path)


def test_modified_model_and_unexpected_path_fail_before_load(tmp_path: Path):
    joblib = pytest.importorskip("joblib")
    model = tmp_path / "model.joblib"
    joblib.dump({"safe": True}, model)
    checksum = hashlib.sha256(model.read_bytes()).hexdigest()
    model.write_bytes(model.read_bytes() + b"modified")
    with pytest.raises(ArtifactIntegrityError, match="checksum"):
        safe_load_joblib(model, checksum, trusted_root=tmp_path)
    with pytest.raises(ArtifactIntegrityError):
        safe_load_joblib(tmp_path / "missing.joblib", checksum, trusted_root=tmp_path)


def test_supported_model_paths_use_trusted_loader():
    for relative in ("src/risk_engine/final_architecture.py", "src/risk_engine/run_development_evaluation.py"):
        source = (ROOT / relative).read_text(encoding="utf-8")
        assert "load_trusted_model" in source
        assert "joblib.load" not in source


def test_monitoring_manifest_outputs_and_privacy_are_intact():
    manifest_path = ROOT / "artifacts/module7_v1_freeze_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    validation = manifest["validation_run"]
    for key in ("manifest", "monitoring_output", "drift_output", "feedback_output"):
        path = ROOT / validation[key]
        assert path.is_file()
        expected = validation[f"{key}_sha256"] if f"{key}_sha256" in validation else manifest["validation_run"]["manifest_sha256"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected
    payload = " ".join((ROOT / validation[key]).read_text(encoding="utf-8") for key in ("monitoring_output", "drift_output", "feedback_output"))
    assert all(secret not in payload for secret in ("isFraud", "isFlaggedFraud", "nameOrig", "nameDest", "reviewer_label", "notes"))


def test_all_frozen_references_remain_unchanged():
    expected = {
        "artifacts/module4_final_holdout_recovery_v1/complete_holdout_scores.csv": "16ab136cab8313db935fb30a6f182ddd15db7de28c9d76bdfa089345a35f9410",
        "artifacts/module5_authoritative_v1/module5_v1_freeze_manifest.json": "cba41469946685007cf475c3bfe2661076b19ca028bc883d1920f724aaa6d83c",
        "artifacts/module6_v1_freeze_manifest.json": "3d286b4f2e5fceca079c294a0be54ff80ad6286c7e1c34bbd687da4c924006fc",
        "artifacts/module7_v1_freeze_manifest.json": "8a6ce8bb8cab6c0437ac3ad63744b907dbf4688957bbf4fcbbc88eec26b280c3",
    }
    for relative, checksum in expected.items():
        assert hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() == checksum

