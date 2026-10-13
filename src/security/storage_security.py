"""Security boundaries for local SQLite, filesystem, and serialized artifacts.

These wrappers sit outside the frozen Modules 4--7 implementation.  They
validate trust boundaries before delegating to existing application helpers.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

REVIEW_STATUSES = (
    "Unreviewed", "Needs Investigation", "False Positive Suspected",
    "Escalated", "Reviewed / Closed",
)


class StorageSecurityError(ValueError):
    """Safe, analyst-facing storage validation error."""


class ArtifactIntegrityError(StorageSecurityError):
    """Trusted artifact verification failed before deserialization."""


def _text_path(value: str | os.PathLike[str]) -> Path:
    if not isinstance(value, (str, os.PathLike)):
        raise StorageSecurityError("path must be text")
    raw = os.fspath(value)
    if not isinstance(raw, str) or not raw or "\x00" in raw or any(ord(c) < 32 for c in raw):
        raise StorageSecurityError("path contains unsupported characters")
    if len(raw) > 4096:
        raise StorageSecurityError("path exceeds the supported length")
    return Path(raw)


def _inside(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def secure_path(
    value: str | os.PathLike[str], *, root: str | os.PathLike[str] | None = None,
    must_exist: bool = False, expected_type: str | None = None,
    reject_symlink: bool = True,
) -> Path:
    """Resolve a path and enforce optional trusted-root/type constraints."""
    candidate = _text_path(value)
    if ".." in candidate.parts:
        raise StorageSecurityError("parent-directory traversal is not accepted")
    if candidate.exists() and reject_symlink and candidate.is_symlink():
        raise StorageSecurityError("symbolic links are not accepted for this operation")
    if must_exist and not candidate.exists():
        raise StorageSecurityError("required source artifact is unavailable")
    if candidate.exists():
        resolved = candidate.resolve(strict=True)
    else:
        parent = candidate.parent
        if not parent.exists() or not parent.is_dir() or (reject_symlink and parent.is_symlink()):
            raise StorageSecurityError("destination directory is unavailable")
        resolved = candidate.resolve()
    if root is not None:
        try:
            trusted = _text_path(root).resolve(strict=True)
        except (OSError, FileNotFoundError) as exc:
            raise StorageSecurityError("trusted directory is unavailable") from exc
        if not trusted.is_dir() or not _inside(resolved, trusted):
            raise StorageSecurityError("path is outside the trusted directory")
    if expected_type == "file" and (not resolved.is_file()):
        raise StorageSecurityError("expected a regular file")
    if expected_type == "directory" and (not resolved.is_dir()):
        raise StorageSecurityError("expected a directory")
    return resolved


def secure_output_path(value: str | os.PathLike[str], *, root: str | os.PathLike[str], suffix: str | None = None) -> Path:
    path = secure_path(value, root=root, must_exist=False, reject_symlink=True)
    if suffix and path.suffix.lower() != suffix.lower():
        raise StorageSecurityError("output file type is not supported")
    if path.exists():
        raise StorageSecurityError("output already exists")
    return path


def publish_json(value: Any, destination: str | os.PathLike[str], *, root: str | os.PathLike[str]) -> Path:
    """Publish JSON without overwriting an existing destination."""
    target = secure_output_path(destination, root=root, suffix=".json")
    payload = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False).encode("utf-8")
    temp = target.with_name(f".{target.name}.tmp-{os.getpid()}")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    try:
        fd = os.open(temp, flags)
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        if target.exists() or target.is_symlink():
            raise StorageSecurityError("output already exists")
        os.replace(temp, target)
    except StorageSecurityError:
        if temp.exists():
            temp.unlink()
        raise
    except OSError as exc:
        if temp.exists():
            temp.unlink()
        raise StorageSecurityError("unable to publish output") from exc
    return target


def validate_feedback_timestamp(value: str) -> str:
    if not isinstance(value, str) or len(value) > 64:
        raise StorageSecurityError("feedback timestamp is invalid")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise StorageSecurityError("feedback timestamp is invalid") from exc
    if parsed.tzinfo is None:
        raise StorageSecurityError("feedback timestamp must include timezone")
    return parsed.astimezone(timezone.utc).isoformat()


def validate_feedback_event(row_id: int, status: str, reviewer_label: str, notes: str | None = None) -> None:
    if isinstance(row_id, bool) or not isinstance(row_id, int) or row_id < 0:
        raise StorageSecurityError("row identifier must be a non-negative integer")
    if not isinstance(status, str) or status not in REVIEW_STATUSES:
        raise StorageSecurityError("review status is unsupported")
    if not isinstance(reviewer_label, str) or not reviewer_label.strip() or len(reviewer_label) > 128:
        raise StorageSecurityError("reviewer label is invalid")
    if notes is not None and (not isinstance(notes, str) or len(notes) > 4000):
        raise StorageSecurityError("review notes exceed the supported length")


def secure_save_review(
    path: str | os.PathLike[str], row_id: int, status: str, reviewer_label: str,
    notes: str | None = None, *, trusted_root: str | os.PathLike[str],
    production_only: bool = False, demonstration_path: str | os.PathLike[str] | None = None,
):
    validate_feedback_event(row_id, status, reviewer_label, notes)
    target = secure_path(path, root=trusted_root, must_exist=False, expected_type=None)
    if production_only and demonstration_path is not None:
        demo = _text_path(demonstration_path).resolve()
        if target == demo:
            raise StorageSecurityError("demonstration database is not writable in production mode")
    try:
        from src.dashboard.feedback_store import save_review
        return save_review(target, row_id, status, reviewer_label, notes)
    except (OSError, sqlite3.Error) as exc:
        raise StorageSecurityError("unable to save feedback event") from exc


def secure_read_sqlite(path: str | os.PathLike[str], *, trusted_root: str | os.PathLike[str],
                       production_only: bool = False,
                       demonstration_path: str | os.PathLike[str] | None = None) -> list[dict[str, Any]]:
    target = secure_path(path, root=trusted_root, must_exist=True, expected_type="file")
    if production_only and demonstration_path is not None and target == _text_path(demonstration_path).resolve():
        raise StorageSecurityError("demonstration database is not permitted for production reads")
    uri = f"file:{target.as_posix()}?mode=ro"
    try:
        with sqlite3.connect(uri, uri=True) as connection:
            rows = connection.execute(
                "SELECT event_id,row_id,status,reviewer_label,notes,created_at_utc "
                "FROM review_events ORDER BY created_at_utc,event_id"
            ).fetchall()
    except (sqlite3.Error, OSError) as exc:
        raise StorageSecurityError("unable to read feedback database") from exc
    result = []
    for event_id, row_id, status, reviewer_label, notes, created_at in rows:
        validate_feedback_event(row_id, status, reviewer_label, notes)
        validate_feedback_timestamp(created_at)
        result.append({"event_id": event_id, "row_id": row_id, "status": status,
                       "reviewer_label": reviewer_label, "notes": notes,
                       "created_at_utc": created_at})
    return result


def sha256_file(path: str | os.PathLike[str], *, trusted_root: str | os.PathLike[str] | None = None) -> str:
    target = secure_path(path, root=trusted_root, must_exist=True, expected_type="file")
    digest = hashlib.sha256()
    with target.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_serialized_artifact(path: str | os.PathLike[str], expected_sha256: str, *, trusted_root: str | os.PathLike[str]) -> Path:
    target = secure_path(path, root=trusted_root, must_exist=True, expected_type="file")
    if target.suffix.lower() not in {".joblib", ".pkl", ".pickle"}:
        raise ArtifactIntegrityError("serialized artifact type is not supported")
    if not isinstance(expected_sha256, str) or len(expected_sha256) != 64:
        raise ArtifactIntegrityError("trusted artifact checksum is invalid")
    actual = sha256_file(target)
    if actual.lower() != expected_sha256.lower():
        raise ArtifactIntegrityError("serialized artifact checksum mismatch")
    return target


def safe_load_joblib(path: str | os.PathLike[str], expected_sha256: str, *, trusted_root: str | os.PathLike[str]) -> Any:
    try:
        target = verify_serialized_artifact(path, expected_sha256, trusted_root=trusted_root)
    except ArtifactIntegrityError:
        raise
    except StorageSecurityError as exc:
        raise ArtifactIntegrityError("trusted serialized artifact is unavailable or untrusted") from exc
    try:
        import joblib
        return joblib.load(target)
    except Exception as exc:  # preserve a safe boundary around deserialization failures
        raise ArtifactIntegrityError("trusted serialized artifact could not be loaded") from exc
