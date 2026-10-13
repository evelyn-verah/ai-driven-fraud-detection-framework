"""Versioned, read-only orchestration for Module 7 Stage 5.

The lifecycle runner composes the existing Stage 2, 3, and 4 calculators.  It
does not read the raw PaySim CSV, rescore transactions, or alter frozen files.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from src.dashboard.config import (
    FEEDBACK_DB_PATH,
    FROZEN_ARCHITECTURE_VERSION,
    FROZEN_THRESHOLD,
    METADATA_INDEX_PATH,
    SCORE_CACHE_PATH,
)
from src.dashboard.metadata_index import load_metadata_index
from src.dashboard.data_access import load_score_cache

from .contracts import MonitoringWindow, validate_windows
from .engine import (
    HOLDOUT_END_STEP,
    HOLDOUT_START_STEP,
    MODULE4_MANIFEST,
    load_frozen_inputs,
    sha256_file,
    summarize_monitoring,
    write_monitoring_result,
)
from .drift import analyze_drift
from .feedback import analyze_feedback

LIFECYCLE_SCHEMA_VERSION = "module7_stage5_monitoring_lifecycle_v1"
CONFIG_SCHEMA_VERSION = "module7_stage5_monitoring_config_v1"
FORBIDDEN_OUTPUT_KEYS = {"isFraud", "isFlaggedFraud", "nameOrig", "nameDest", "reviewer_label", "notes"}


def _window(value: Mapping[str, Any]) -> MonitoringWindow:
    return MonitoringWindow(
        window_id=str(value["window_id"]),
        start_step=int(value["start_step"]),
        end_step=int(value["end_step"]),
        purpose=str(value["purpose"]),
        selection_rationale=str(value["selection_rationale"]),
        created_at_utc=str(value.get("created_at_utc", "")),
        source_versions=dict(value.get("source_versions", {})),
    )


@dataclass(frozen=True)
class MonitoringLifecycleConfig:
    run_id: str
    reference_window: MonitoringWindow
    comparison_window: MonitoringWindow
    summary_windows: tuple[MonitoringWindow, ...]
    output_dir: Path
    score_cache_path: Path = SCORE_CACHE_PATH
    metadata_sidecar_path: Path = METADATA_INDEX_PATH
    feedback_enabled: bool = False
    feedback_db_path: Path = FEEDBACK_DB_PATH
    frozen_model_version: str = FROZEN_ARCHITECTURE_VERSION
    frozen_threshold: float = FROZEN_THRESHOLD
    schema_version: str = CONFIG_SCHEMA_VERSION

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "MonitoringLifecycleConfig":
        summary = tuple(_window(item) for item in value.get("summary_windows", []))
        if not summary:
            summary = (_window(value["reference_window"]), _window(value["comparison_window"]))
        result = cls(
            run_id=str(value["run_id"]),
            reference_window=_window(value["reference_window"]),
            comparison_window=_window(value["comparison_window"]),
            summary_windows=summary,
            output_dir=Path(value["output_dir"]),
            score_cache_path=Path(value.get("score_cache_path", SCORE_CACHE_PATH)),
            metadata_sidecar_path=Path(value.get("metadata_sidecar_path", METADATA_INDEX_PATH)),
            feedback_enabled=bool(value.get("feedback_enabled", False)),
            feedback_db_path=Path(value.get("feedback_db_path", FEEDBACK_DB_PATH)),
            frozen_model_version=str(value.get("frozen_model_version", FROZEN_ARCHITECTURE_VERSION)),
            frozen_threshold=float(value.get("frozen_threshold", FROZEN_THRESHOLD)),
            schema_version=str(value.get("schema_version", CONFIG_SCHEMA_VERSION)),
        )
        validate_config(result)
        return result

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "run_id": self.run_id,
            "reference_window": self.reference_window.to_dict(),
            "comparison_window": self.comparison_window.to_dict(),
            "summary_windows": [window.to_dict() for window in self.summary_windows],
            "output_dir": str(self.output_dir),
            "score_cache_path": str(self.score_cache_path),
            "metadata_sidecar_path": str(self.metadata_sidecar_path),
            "feedback_enabled": self.feedback_enabled,
            "feedback_db_path": str(self.feedback_db_path),
            "frozen_model_version": self.frozen_model_version,
            "frozen_threshold": self.frozen_threshold,
        }


def validate_config(config: MonitoringLifecycleConfig) -> MonitoringLifecycleConfig:
    if config.schema_version != CONFIG_SCHEMA_VERSION:
        raise ValueError(f"unsupported configuration schema: {config.schema_version}")
    if not config.run_id or any(ch in config.run_id for ch in "\\/:*?\"<>|"):
        raise ValueError("run_id must be non-empty and path-safe")
    if config.frozen_model_version != FROZEN_ARCHITECTURE_VERSION:
        raise ValueError("frozen model version does not match the approved architecture")
    if config.frozen_threshold != FROZEN_THRESHOLD:
        raise ValueError("frozen threshold does not match the approved threshold")
    if config.reference_window.end_step >= config.comparison_window.start_step:
        raise ValueError("reference and comparison windows must be ordered and non-overlapping")
    validate_windows([config.reference_window, config.comparison_window])
    validate_windows(config.summary_windows)
    if not config.score_cache_path.is_file():
        raise FileNotFoundError(f"score cache not found: {config.score_cache_path}")
    if not config.metadata_sidecar_path.is_dir():
        raise FileNotFoundError(f"metadata sidecar not found: {config.metadata_sidecar_path}")
    if config.feedback_enabled and not config.feedback_db_path.is_file():
        raise FileNotFoundError(f"feedback database not found: {config.feedback_db_path}")
    return config


def load_config(path: str | Path) -> MonitoringLifecycleConfig:
    """Load and validate a versioned JSON lifecycle configuration."""
    with Path(path).open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, Mapping):
        raise ValueError("monitoring configuration must be a JSON object")
    return MonitoringLifecycleConfig.from_mapping(value)


def _write_json(path: Path, value: Mapping[str, Any], *, overwrite: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not overwrite:
        raise FileExistsError(f"refusing to overwrite existing artifact: {path}")
    fd, temporary = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(value, handle, indent=2, sort_keys=True, allow_nan=False)
            handle.write("\n")
        os.replace(temporary, path)
    except Exception:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def _checksums(paths: list[Path]) -> dict[str, Any]:
    result = {}
    for path in paths:
        result[str(path)] = {"exists": path.exists(), "sha256": sha256_file(path) if path.is_file() else None}
    return result


def _assert_private(value: Any) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if key in FORBIDDEN_OUTPUT_KEYS:
                raise ValueError(f"forbidden privacy field in monitoring output: {key}")
            _assert_private(child)
    elif isinstance(value, list):
        for child in value:
            _assert_private(child)


def run_monitoring(config: MonitoringLifecycleConfig | Mapping[str, Any], *, input_loader=None) -> dict[str, Any]:
    """Run one immutable monitoring lifecycle and publish a manifest."""
    if not isinstance(config, MonitoringLifecycleConfig):
        config = MonitoringLifecycleConfig.from_mapping(config)
    validate_config(config)
    run_dir = config.output_dir / config.run_id
    if run_dir.exists():
        raise FileExistsError(f"monitoring run already exists: {run_dir}")
    run_dir.mkdir(parents=True)
    started = time.perf_counter()
    timestamp = datetime.now(timezone.utc).isoformat()
    manifest: dict[str, Any] = {
        "schema_version": LIFECYCLE_SCHEMA_VERSION,
        "run_id": config.run_id,
        "status": "running",
        "started_at_utc": timestamp,
        "configuration": config.to_dict(),
        "limitations": [
            "Retrospective descriptive monitoring over simulated PaySim data.",
            "Analyst feedback is mutable workflow information, not verified fraud ground truth.",
            "Monitoring does not retrain, rescore, recalibrate, or modify frozen artifacts.",
        ],
    }
    manifest_path = run_dir / "manifest.json"
    try:
        loader = input_loader or load_frozen_inputs
        frame, metadata, source = loader(include_metadata=True)
        if Path(source.get("score_cache_path", config.score_cache_path)).resolve() != config.score_cache_path.resolve():
            raise ValueError("loaded score cache does not match configured source")
        if float(source.get("frozen_threshold", FROZEN_THRESHOLD)) != config.frozen_threshold:
            raise ValueError("loaded threshold does not match configured threshold")
        summary = summarize_monitoring(
            frame, metadata, list(config.summary_windows), source, config.frozen_threshold, source["complete_step_counts"]
        )
        drift = analyze_drift(
            frame, metadata, config.reference_window, config.comparison_window,
            source["complete_step_counts"], source, config.frozen_threshold
        )
        outputs: dict[str, Any] = {"monitoring": summary, "drift": drift}
        if config.feedback_enabled:
            outputs["feedback"] = analyze_feedback(config.feedback_db_path, frame, threshold=config.frozen_threshold)
        for name, value in outputs.items():
            _assert_private(value)
            _write_json(run_dir / f"{name}.json", value)
        output_paths = {name: str(run_dir / f"{name}.json") for name in outputs}
        output_checksums = {name: sha256_file(Path(path)) for name, path in output_paths.items()}
        feedback_snapshot = {"enabled": config.feedback_enabled}
        if config.feedback_enabled:
            feedback_source = outputs["feedback"].get("source_database", {})
            feedback_snapshot.update({"path": str(config.feedback_db_path), "status": feedback_source.get("status")})
            if config.feedback_db_path.is_file():
                stat = config.feedback_db_path.stat()
                feedback_snapshot.update({"sha256": sha256_file(config.feedback_db_path), "file_size_bytes": stat.st_size, "mtime_utc": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(), "read_consistency": "single read-only SQLite connection"})
        manifest.update({
            "status": "completed",
            "completed_at_utc": datetime.now(timezone.utc).isoformat(),
            "runtime_seconds": time.perf_counter() - started,
            "source_artifacts": {**source, "configured_score_cache_sha256": sha256_file(config.score_cache_path)},
            "frozen_input_checksums": _checksums([config.score_cache_path, config.metadata_sidecar_path / "manifest.json", MODULE4_MANIFEST]),
            "output_paths": output_paths,
            "output_checksums": output_checksums,
            "feedback": feedback_snapshot,
        })
        _write_json(manifest_path, manifest)
        return manifest
    except Exception as exc:
        manifest.update({"status": "failed", "completed_at_utc": datetime.now(timezone.utc).isoformat(), "runtime_seconds": time.perf_counter() - started, "error": {"type": type(exc).__name__, "message": str(exc)}})
        _write_json(manifest_path, manifest, overwrite=True)
        raise


__all__ = ["CONFIG_SCHEMA_VERSION", "LIFECYCLE_SCHEMA_VERSION", "MonitoringLifecycleConfig", "load_config", "validate_config", "run_monitoring"]
