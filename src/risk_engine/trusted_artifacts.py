"""Trusted Module 4 model-artifact loading boundary.

Expected hashes are versioned in source control and independently recorded in
the frozen Module 4 recovery manifest. They are never read from the artifact
being verified or accepted from a caller at runtime.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from src.security.storage_security import ArtifactIntegrityError, safe_load_joblib, secure_path


ROOT = Path(__file__).resolve().parents[2]


TRUSTED_MODEL_ARTIFACTS = {
    "supervised": (
        Path("artifacts/paysim_v2/random_forest.joblib"),
        "0292f5ea763cf436bbf324b7d8f028a3791f9c31927717bd9026afaedecffbf5",
    ),
    "baseline_anomaly": (
        Path("artifacts/anomaly_detection_behavioral_1m/isolation_forest_baseline_matched.joblib"),
        "30b5c1d8d18a1a84ba4dc8b176f35377567f88130c77e555064ac70e2983b59a",
    ),
    "behavioral_anomaly": (
        Path("artifacts/anomaly_detection_behavioral_1m/isolation_forest_behavioral.joblib"),
        "8fa657f3224918e7aa324b76a8f526818e2ade669db352a6eb7b60ec2fa75173",
    ),
}


def load_trusted_model(path: str | Path, *, model_role: str) -> Any:
    """Load one exact frozen model only after source-controlled hash verification."""
    if model_role not in TRUSTED_MODEL_ARTIFACTS:
        raise ArtifactIntegrityError("model role is not trusted")
    relative, expected_sha256 = TRUSTED_MODEL_ARTIFACTS[model_role]
    expected_path = (ROOT / relative).resolve()
    try:
        supplied = Path(path).resolve()
    except (OSError, TypeError) as exc:
        raise ArtifactIntegrityError("model path is invalid") from exc
    if supplied != expected_path:
        raise ArtifactIntegrityError("model path is not an approved frozen artifact")
    verified = secure_path(supplied, root=ROOT, must_exist=True, expected_type="file")
    return safe_load_joblib(verified, expected_sha256, trusted_root=ROOT)


__all__ = ["TRUSTED_MODEL_ARTIFACTS", "load_trusted_model"]
