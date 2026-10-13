from __future__ import annotations

import hashlib
import os
import sqlite3
from pathlib import Path

import pytest

from src.security.storage_security import (
    ArtifactIntegrityError,
    StorageSecurityError,
    publish_json,
    safe_load_joblib,
    secure_output_path,
    secure_read_sqlite,
    secure_save_review,
    sha256_file,
    verify_serialized_artifact,
)


def test_valid_sqlite_write_read_and_parameterized_data(tmp_path: Path):
    db = tmp_path / "reviews.sqlite3"
    event = secure_save_review(db, 4, "Reviewed / Closed", "reviewer", "value'); DROP TABLE review_events;--", trusted_root=tmp_path)
    rows = secure_read_sqlite(db, trusted_root=tmp_path)
    assert rows[0]["event_id"] == event.event_id
    assert rows[0]["notes"].startswith("value')")


@pytest.mark.parametrize("status", ["bad", "Escalated' OR 1=1 --"])
def test_invalid_status_rejected(status: str, tmp_path: Path):
    with pytest.raises(StorageSecurityError):
        secure_save_review(tmp_path / "x.sqlite3", 1, status, "analyst", trusted_root=tmp_path)


def test_invalid_feedback_fields_and_timestamp(tmp_path: Path):
    with pytest.raises(StorageSecurityError):
        secure_save_review(tmp_path / "x.sqlite3", -1, "Unreviewed", "analyst", trusted_root=tmp_path)
    from src.security.storage_security import validate_feedback_timestamp
    with pytest.raises(StorageSecurityError):
        validate_feedback_timestamp("2026-01-01T00:00:00")


def test_read_only_sqlite_does_not_modify_database(tmp_path: Path):
    db = tmp_path / "reviews.sqlite3"
    secure_save_review(db, 1, "Unreviewed", "analyst", trusted_root=tmp_path)
    before = sha256_file(db)
    rows = secure_read_sqlite(db, trusted_root=tmp_path)
    assert len(rows) == 1 and sha256_file(db) == before
    uri = f"file:{db.resolve().as_posix()}?mode=ro"
    with sqlite3.connect(uri, uri=True) as connection:
        with pytest.raises(sqlite3.OperationalError):
            connection.execute("INSERT INTO review_events VALUES ('x',2,'Unreviewed','a',NULL,'2026-01-01T00:00:00+00:00')")


def test_missing_and_malformed_sqlite_are_safe(tmp_path: Path):
    with pytest.raises(StorageSecurityError, match="unavailable"):
        secure_read_sqlite(tmp_path / "missing.sqlite3", trusted_root=tmp_path)
    malformed = tmp_path / "bad.sqlite3"
    malformed.write_bytes(b"not sqlite")
    with pytest.raises(StorageSecurityError, match="unable to read"):
        secure_read_sqlite(malformed, trusted_root=tmp_path)


def test_demo_database_isolation(tmp_path: Path):
    demo = tmp_path / "demo.sqlite3"
    secure_save_review(demo, 1, "Unreviewed", "analyst", trusted_root=tmp_path)
    with pytest.raises(StorageSecurityError, match="demonstration"):
        secure_read_sqlite(demo, trusted_root=tmp_path, production_only=True, demonstration_path=demo)
    with pytest.raises(StorageSecurityError, match="demonstration"):
        secure_save_review(demo, 2, "Unreviewed", "analyst", trusted_root=tmp_path, production_only=True, demonstration_path=demo)


def test_path_traversal_and_invalid_types_rejected(tmp_path: Path):
    with pytest.raises(StorageSecurityError):
        secure_output_path(tmp_path / ".." / "escape.json", root=tmp_path)
    with pytest.raises(StorageSecurityError, match="regular file"):
        sha256_file(tmp_path, trusted_root=tmp_path)
    with pytest.raises(StorageSecurityError, match="trusted"):
        secure_output_path(tmp_path.parent / "escape.json", root=tmp_path)


def test_symlink_escape_rejected_when_supported(tmp_path: Path):
    outside = tmp_path.parent / "outside.txt"
    outside.write_text("x", encoding="utf-8")
    link = tmp_path / "link.txt"
    try:
        link.symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation unavailable")
    with pytest.raises(StorageSecurityError):
        sha256_file(link, trusted_root=tmp_path)


def test_output_collision_is_rejected(tmp_path: Path):
    target = tmp_path / "out.json"
    target.write_text("existing", encoding="utf-8")
    with pytest.raises(StorageSecurityError, match="already exists"):
        publish_json({"ok": True}, target, root=tmp_path)
    created = publish_json({"ok": True}, tmp_path / "new.json", root=tmp_path)
    assert created.read_text(encoding="utf-8").strip().startswith("{")


def test_serialized_artifact_checksum_and_trusted_path(tmp_path: Path):
    joblib = pytest.importorskip("joblib")
    artifact = tmp_path / "model.joblib"
    joblib.dump({"safe": True}, artifact)
    checksum = hashlib.sha256(artifact.read_bytes()).hexdigest()
    assert verify_serialized_artifact(artifact, checksum, trusted_root=tmp_path) == artifact.resolve()
    assert safe_load_joblib(artifact, checksum, trusted_root=tmp_path) == {"safe": True}
    with pytest.raises(ArtifactIntegrityError, match="checksum"):
        safe_load_joblib(artifact, "0" * 64, trusted_root=tmp_path)
    with pytest.raises(StorageSecurityError, match="trusted"):
        verify_serialized_artifact(artifact, checksum, trusted_root=tmp_path / "other")


def test_untrusted_serialized_types_rejected(tmp_path: Path):
    p = tmp_path / "model.txt"
    p.write_text("payload", encoding="utf-8")
    with pytest.raises(ArtifactIntegrityError, match="type"):
        verify_serialized_artifact(p, hashlib.sha256(p.read_bytes()).hexdigest(), trusted_root=tmp_path)


def test_frozen_artifacts_preserved():
    root = Path(__file__).resolve().parents[1]
    expected = {
        root / "artifacts/module4_final_holdout_recovery_v1/complete_holdout_scores.csv": "16ab136cab8313db935fb30a6f182ddd15db7de28c9d76bdfa089345a35f9410",
        root / "artifacts/module5_authoritative_v1/module5_v1_freeze_manifest.json": "cba41469946685007cf475c3bfe2661076b19ca028bc883d1920f724aaa6d83c",
        root / "artifacts/module6_v1_freeze_manifest.json": "3d286b4f2e5fceca079c294a0be54ff80ad6286c7e1c34bbd687da4c924006fc",
        root / "artifacts/module7_v1_freeze_manifest.json": "8a6ce8bb8cab6c0437ac3ad63744b907dbf4688957bbf4fcbbc88eec26b280c3",
    }
    for path, checksum in expected.items():
        assert sha256_file(path) == checksum
