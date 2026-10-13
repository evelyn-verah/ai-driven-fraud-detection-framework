from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from src.risk_engine.trusted_artifacts import TRUSTED_MODEL_ARTIFACTS, load_trusted_model
from src.security.storage_security import ArtifactIntegrityError, safe_load_joblib


def _known_artifact(tmp_path: Path) -> tuple[Path, str]:
    joblib = pytest.importorskip("joblib")
    path = tmp_path / "known.joblib"
    joblib.dump({"safe": True}, path)
    return path, hashlib.sha256(path.read_bytes()).hexdigest()


def test_valid_trusted_artifact_loads():
    role = "supervised"
    path = Path(TRUSTED_MODEL_ARTIFACTS[role][0])
    loaded = load_trusted_model(path, model_role=role)
    assert loaded is not None


def test_modified_artifact_rejected_before_deserialization(tmp_path: Path):
    path, checksum = _known_artifact(tmp_path)
    path.write_bytes(path.read_bytes() + b"tampered")
    with pytest.raises(ArtifactIntegrityError, match="checksum"):
        safe_load_joblib(path, checksum, trusted_root=tmp_path)


def test_missing_and_incorrect_checksums_rejected(tmp_path: Path):
    path, checksum = _known_artifact(tmp_path)
    with pytest.raises(ArtifactIntegrityError):
        safe_load_joblib(path, None, trusted_root=tmp_path)  # type: ignore[arg-type]
    with pytest.raises(ArtifactIntegrityError, match="checksum"):
        safe_load_joblib(path, "0" * 64, trusted_root=tmp_path)
    assert checksum != "0" * 64


def test_missing_model_file_handled_safely(tmp_path: Path):
    with pytest.raises(ArtifactIntegrityError, match="unavailable|regular file"):
        safe_load_joblib(tmp_path / "missing.joblib", "0" * 64, trusted_root=tmp_path)


def test_unexpected_path_and_untrusted_role_rejected(tmp_path: Path):
    path, _ = _known_artifact(tmp_path)
    with pytest.raises(ArtifactIntegrityError, match="approved"):
        load_trusted_model(path, model_role="supervised")
    with pytest.raises(ArtifactIntegrityError, match="role"):
        load_trusted_model(Path(TRUSTED_MODEL_ARTIFACTS["supervised"][0]), model_role="attacker")


def test_error_does_not_disclose_path_or_contents(tmp_path: Path):
    secret_path = tmp_path / "secret-account-model.joblib"
    secret_path.write_bytes(b"private-model-content")
    with pytest.raises(ArtifactIntegrityError) as exc:
        load_trusted_model(secret_path, model_role="supervised")
    assert "secret-account-model" not in str(exc.value)
    assert "private-model-content" not in str(exc.value)


def test_actual_risk_entry_points_use_verified_loader():
    root = Path(__file__).resolve().parents[1]
    final_source = (root / "src/risk_engine/final_architecture.py").read_text(encoding="utf-8")
    dev_source = (root / "src/risk_engine/run_development_evaluation.py").read_text(encoding="utf-8")
    assert "load_trusted_model" in final_source and "joblib.load" not in final_source
    assert "load_trusted_model" in dev_source and "joblib.load" not in dev_source


def test_trusted_checksum_values_match_frozen_recovery_manifest():
    import json
    root = Path(__file__).resolve().parents[1]
    recovery = json.loads((root / "artifacts/module4_final_holdout_recovery_v1/recovery_manifest.json").read_text())
    recorded = recovery["frozen_manifest"]["model_sha256"]
    assert {role: checksum for role, (_, checksum) in TRUSTED_MODEL_ARTIFACTS.items()} == recorded

