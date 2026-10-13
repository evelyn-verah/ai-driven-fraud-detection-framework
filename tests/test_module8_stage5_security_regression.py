from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.security.dashboard_access import AuthorizationError, authorized_detail, authorized_scores, issue_local_context
from src.security.input_validation import InputSecurityError, validate_monitoring_request, validate_paysim_frame
from src.security.storage_security import (
    ArtifactIntegrityError,
    StorageSecurityError,
    publish_json,
    safe_load_joblib,
    secure_read_sqlite,
    secure_save_review,
    sha256_file,
)


def test_input_boundaries_and_safe_errors():
    frame = pd.DataFrame({"step": [378], "type": ["PAYMENT"], "amount": [10.0],
                          "oldbalanceOrg": [10.0], "newbalanceOrig": [0.0],
                          "oldbalanceDest": [0.0], "newbalanceDest": [10.0]})
    assert validate_paysim_frame(frame).equals(frame)
    bad = frame.copy()
    bad.loc[0, "amount"] = np.inf
    with pytest.raises(InputSecurityError) as exc:
        validate_paysim_frame(bad)
    assert "inf" not in str(exc.value).lower()
    with pytest.raises(InputSecurityError):
        validate_monitoring_request(378, 378 + 1000)


def test_oversized_transaction_and_invalid_category_rejected():
    frame = pd.DataFrame({"step": [378], "type": ["UNKNOWN"], "amount": [-1.0],
                          "oldbalanceOrg": [1.0], "newbalanceOrig": [2.0],
                          "oldbalanceDest": [0.0], "newbalanceDest": [0.0]})
    with pytest.raises(InputSecurityError):
        validate_paysim_frame(frame)


def test_sqlite_injection_read_only_and_isolation(tmp_path: Path):
    db = tmp_path / "production.sqlite3"
    demo = tmp_path / "demo.sqlite3"
    secure_save_review(db, 1, "Unreviewed", "a'); DROP TABLE review_events;--", "note", trusted_root=tmp_path)
    rows = secure_read_sqlite(db, trusted_root=tmp_path)
    assert len(rows) == 1
    secure_save_review(demo, 2, "Unreviewed", "demo", trusted_root=tmp_path)
    with pytest.raises(StorageSecurityError):
        secure_read_sqlite(demo, trusted_root=tmp_path, production_only=True, demonstration_path=demo)


def test_filesystem_traversal_and_collision_protection(tmp_path: Path):
    with pytest.raises(StorageSecurityError):
        publish_json({}, tmp_path / ".." / "escape.json", root=tmp_path)
    target = publish_json({"ok": True}, tmp_path / "result.json", root=tmp_path)
    with pytest.raises(StorageSecurityError):
        publish_json({}, target, root=tmp_path)


def test_artifact_checksum_mismatch_rejected_without_loading(tmp_path: Path):
    joblib = pytest.importorskip("joblib")
    artifact = tmp_path / "known.joblib"
    joblib.dump({"safe": True}, artifact)
    with pytest.raises(ArtifactIntegrityError):
        safe_load_joblib(artifact, "0" * 64, trusted_root=tmp_path)
    checksum = hashlib.sha256(artifact.read_bytes()).hexdigest()
    assert safe_load_joblib(artifact, checksum, trusted_root=tmp_path) == {"safe": True}


def test_unauthorized_dashboard_reads_and_forged_contexts_denied():
    rows = pd.DataFrame({"row_id": [0], "step": [378], "fraud_probability": [0.5],
                         "baseline_anomaly_intensity": [0.1], "behavioral_anomaly_intensity": [0.2],
                         "rule_score_context": [0.0], "alert": [True], "isFraud": [1]})
    with pytest.raises(AuthorizationError):
        authorized_scores(None, rows)
    with pytest.raises(AuthorizationError):
        authorized_scores(type("Forged", (), {"role": "Administrator", "authenticated": True})(), rows)


def test_sensitive_field_exclusion():
    context = issue_local_context("Viewer", trusted_local_identity=True)
    detail = {"metadata": {"row_id": 0, "step": 378, "amount": 1.0, "isFraud": 1,
                            "nameOrig": "sender", "nameDest": "receiver"},
              "intelligence": {"context": {"fraud_probability": 0.2, "isFraud": 1},
                               "explanation": {"observed_facts": ["amount"], "notes": "hidden"}},
              "reviewer_label": "hidden", "notes": "hidden"}
    safe = authorized_detail(context, detail)
    serialized = str(safe)
    for value in ("isFraud", "sender", "receiver", "hidden"):
        assert value not in serialized


def test_actual_entrypoints_show_unintegrated_bypass_paths():
    root = Path(__file__).resolve().parents[1]
    app = (root / "src/dashboard/app.py").read_text(encoding="utf-8")
    historical = (root / "artifacts/module6_v1_1/v1_source_snapshot/src/dashboard/app.py").read_text(encoding="utf-8")
    loader = (root / "src/risk_engine/final_architecture.py").read_text(encoding="utf-8")
    assert "streamlit_main" in app
    assert "load_score_cache" not in app and "save_review" not in app and "review_history" not in app
    assert "load_score_cache" in historical and "save_review" in historical and "review_history" in historical
    assert "load_trusted_model" in loader
    assert "joblib.load" not in loader


def test_frozen_artifact_preservation():
    root = Path(__file__).resolve().parents[1]
    expected = {
        root / "artifacts/module4_final_holdout_recovery_v1/complete_holdout_scores.csv": "16ab136cab8313db935fb30a6f182ddd15db7de28c9d76bdfa089345a35f9410",
        root / "artifacts/module5_authoritative_v1/module5_v1_freeze_manifest.json": "cba41469946685007cf475c3bfe2661076b19ca028bc883d1920f724aaa6d83c",
        root / "artifacts/module6_v1_freeze_manifest.json": "3d286b4f2e5fceca079c294a0be54ff80ad6286c7e1c34bbd687da4c924006fc",
        root / "artifacts/module7_v1_freeze_manifest.json": "8a6ce8bb8cab6c0437ac3ad63744b907dbf4688957bbf4fcbbc88eec26b280c3",
    }
    for path, checksum in expected.items():
        assert sha256_file(path) == checksum
