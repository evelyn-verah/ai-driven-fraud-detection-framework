"""Safe, resumable recovery for the interrupted Module 4 holdout run.

The interrupted prefix is treated as immutable input. Recovery writes a new
artifact directory, checkpoints one complete step at a time, and only combines
the prefix and suffix after all integrity checks pass.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import time
import tracemalloc
import ctypes
from ctypes import wintypes
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, confusion_matrix, f1_score, precision_score, recall_score, roc_auc_score

from src.anomaly_detection.behavioral_features import BEHAVIORAL_FEATURES
from src.risk_engine.behavioral_state import iter_complete_steps
from src.risk_engine.contracts import PAYSIM_MODEL_FEATURES
from src.risk_engine.final_architecture import (
    CALIBRATED_RF_ALERT_THRESHOLD,
    FINAL_ARCHITECTURE_VERSION,
    FinalRiskAssessment,
    FinalRiskAssessmentConfig,
)
from src.risk_engine.scorers import ANOMALY_BASE_FEATURES, ANOMALY_BEHAVIORAL_FEATURES


RECOVERY_VERSION = "module4_final_holdout_recovery_v1"
PERSISTED_SCORE_ATOL = 1e-12
PREFIX_END_STEP = 428
HOLDOUT_END_STEP = 743
EXPECTED_TOTAL_ROWS = 955_744
PREFIX_COLUMNS = (
    "row_id", "step", "isFraud", "fraud_probability",
    "baseline_anomaly_intensity", "behavioral_anomaly_intensity",
    "rule_score_context", "alert",
)
MODEL_SHA256 = {
    "supervised": "0292F5EA763CF436BBF324B7D8F028A3791F9C31927717BD9026AFAEDECFFBF5",
    "baseline_anomaly": "30B5C1D8D18A1A84BA4DC8B176F35377567F88130C77E555064AC70E2983B59A",
    "behavioral_anomaly": "8FA657F3224918E7AA324B76A8F526818E2ADE669DB352A6EB7B60EC2FA75173",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def _atomic_csv(path: Path, frame: pd.DataFrame) -> None:
    temporary = path.with_name(path.name + ".tmp")
    frame.to_csv(temporary, index=False)
    os.replace(temporary, path)


def compare_persisted_scores(
    regenerated: pd.DataFrame,
    persisted: pd.DataFrame,
    *,
    expected_steps: np.ndarray,
    expected_labels: np.ndarray,
) -> dict[str, float]:
    """Compare persisted scores with zero relative and 1e-12 absolute tolerance.

    Row order, steps, labels, and alert decisions remain exact; tolerance applies
    only to serialized floating-point model scores.
    """

    if len(regenerated) != len(persisted) or not np.array_equal(persisted["step"].to_numpy(), expected_steps):
        raise ValueError("Persisted score rows are misaligned")
    if not np.array_equal(persisted["isFraud"].to_numpy(), expected_labels):
        raise ValueError("Persisted score labels differ")
    score_columns = ["fraud_probability", "baseline_anomaly_intensity", "behavioral_anomaly_intensity", "rule_score_context"]
    differences = {
        column: float(np.max(np.abs(regenerated[column].to_numpy(dtype=float) - persisted[column].to_numpy(dtype=float))))
        for column in score_columns
    }
    if not np.array_equal(regenerated["alert"].to_numpy(), persisted["alert"].to_numpy()):
        raise ValueError("Persisted alert decisions differ")
    if any(value > PERSISTED_SCORE_ATOL for value in differences.values()):
        raise ValueError(f"Persisted model score difference exceeds tolerance: {differences}")
    return differences


def verify_frozen_inputs(model_paths: dict[str, Path]) -> dict[str, Any]:
    """Verify the Stage 4 architecture, feature contract, threshold, and models."""

    config = FinalRiskAssessmentConfig()
    if config.architecture_version != FINAL_ARCHITECTURE_VERSION:
        raise ValueError("Unexpected final architecture version")
    if config.fraud_alert_threshold != CALIBRATED_RF_ALERT_THRESHOLD:
        raise ValueError("Frozen Random Forest threshold changed")
    if "steps 46-200" not in config.threshold_provenance:
        raise ValueError("Threshold provenance is not calibration-only")
    actual_hashes = {name: _sha256(path) for name, path in model_paths.items()}
    if {name: value.upper() for name, value in actual_hashes.items()} != MODEL_SHA256:
        raise ValueError(f"Frozen model artifact hash mismatch: {actual_hashes}")
    return {
        "architecture_version": config.architecture_version,
        "threshold": config.fraud_alert_threshold,
        "threshold_provenance": config.threshold_provenance,
        "model_sha256": actual_hashes,
        "supervised_features": list(PAYSIM_MODEL_FEATURES),
        "baseline_anomaly_features": list(ANOMALY_BASE_FEATURES),
        "behavioral_anomaly_features": list(ANOMALY_BEHAVIORAL_FEATURES),
        "behavioral_feature_definitions": list(BEHAVIORAL_FEATURES),
    }


def verify_prefix_cache(
    raw_path: str | Path,
    prefix_path: str | Path,
    *,
    prefix_end_step: int = PREFIX_END_STEP,
) -> dict[str, Any]:
    """Compare immutable prefix row counts, order, IDs, and labels with raw data."""

    cache = pd.read_csv(prefix_path)
    missing = sorted(set(PREFIX_COLUMNS).difference(cache.columns))
    if missing:
        raise ValueError(f"Prefix cache missing columns: {missing}")
    if len(cache) == 0 or cache["row_id"].duplicated().any():
        raise ValueError("Prefix cache row IDs must be non-empty and unique")
    if not np.array_equal(cache["row_id"].to_numpy(), np.arange(len(cache))):
        raise ValueError("Prefix cache row IDs are not sequential")
    if not cache["step"].is_monotonic_increasing or not cache["step"].between(378, prefix_end_step).all():
        raise ValueError("Prefix cache steps are outside the expected ordered range")
    if not cache["isFraud"].isin([0, 1]).all():
        raise ValueError("Prefix cache labels are not binary")
    score_columns = PREFIX_COLUMNS[3:7]
    if not np.isfinite(cache[list(score_columns)].to_numpy(dtype=float)).all():
        raise ValueError("Prefix cache contains non-finite scores")
    cursor = 0
    raw_rows = 0
    seen_steps: list[int] = []
    for step_frame in iter_complete_steps(str(raw_path), chunksize=100_000, include_target=True):
        step = int(step_frame["step"].iloc[0])
        if step > prefix_end_step:
            break
        if step < 378:
            continue
        seen_steps.append(step)
        cached = cache.iloc[cursor:cursor + len(step_frame)]
        if len(cached) != len(step_frame) or not np.array_equal(cached["step"].to_numpy(), step_frame["step"].to_numpy()):
            raise ValueError(f"Prefix row alignment mismatch at step {step}")
        if not np.array_equal(cached["isFraud"].to_numpy(), step_frame["isFraud"].to_numpy()):
            raise ValueError(f"Prefix label mismatch at step {step}")
        cursor += len(step_frame)
        raw_rows += len(step_frame)
    if cursor != len(cache) or raw_rows != len(cache):
        raise ValueError(f"Prefix row count mismatch: raw={raw_rows}, cache={len(cache)}")
    if set(seen_steps) != set(range(378, prefix_end_step + 1)):
        raise ValueError("Prefix cache does not contain every complete step")
    return {
        "prefix_rows": len(cache),
        "first_step": int(cache["step"].min()),
        "last_step": int(cache["step"].max()),
        "raw_alignment": True,
    }


def initialize_recovery(
    recovery_dir: str | Path,
    prefix_path: str | Path,
    *,
    frozen_manifest: dict[str, Any],
    prefix_manifest: dict[str, Any],
) -> dict[str, Any]:
    """Create a new recovery directory and copy the prefix without modifying it."""

    destination = Path(recovery_dir)
    if destination.exists():
        raise FileExistsError(f"Refusing to overwrite recovery directory: {destination}")
    destination.mkdir(parents=True)
    shutil.copy2(prefix_path, destination / "preserved_prefix_scores.csv")
    manifest = {
        "version": RECOVERY_VERSION,
        "last_completed_step": PREFIX_END_STEP,
        "prefix_source": str(Path(prefix_path)),
        "prefix_manifest": prefix_manifest,
        "frozen_manifest": frozen_manifest,
        "checkpoint_files": [],
    }
    _atomic_json(destination / "recovery_manifest.json", manifest)
    return manifest


def resume_suffix(
    raw_path: str | Path,
    recovery_dir: str | Path,
    *,
    model_paths: dict[str, Path],
    prefix_end_step: int = PREFIX_END_STEP,
    end_step: int = HOLDOUT_END_STEP,
) -> dict[str, Any]:
    """Replay state and checkpoint only missing complete steps atomically."""

    destination = Path(recovery_dir)
    manifest_path = destination / "recovery_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assessor = FinalRiskAssessment.from_joblib_paths(
        model_paths["supervised"], model_paths["baseline_anomaly"], model_paths["behavioral_anomaly"]
    )
    last_completed = int(manifest["last_completed_step"])
    prefix_rows = int(manifest["prefix_manifest"]["prefix_rows"])
    row_id = prefix_rows
    seen_steps: list[int] = []
    for step_frame in iter_complete_steps(str(raw_path), chunksize=100_000, include_target=True):
        step = int(step_frame["step"].iloc[0])
        if step > end_step:
            break
        if step <= prefix_end_step:
            assessor.process_history_state_only(step_frame)
            continue
        if step <= last_completed:
            checkpoint = destination / f"step_{step:04d}.csv"
            if not checkpoint.exists():
                raise ValueError(f"Manifest claims missing checkpoint: {checkpoint}")
            assessor.process_history_state_only(step_frame)
            row_id += len(pd.read_csv(checkpoint, usecols=["row_id"]))
            seen_steps.append(step)
            continue
        scored = assessor.assess_step(step_frame)
        checkpoint = pd.DataFrame({
            "row_id": np.arange(row_id, row_id + len(step_frame), dtype="int64"),
            "step": step_frame["step"].to_numpy(dtype="int16"),
            "isFraud": step_frame["isFraud"].to_numpy(dtype="int8"),
            "fraud_probability": scored["fraud_probability"].to_numpy(dtype=float),
            "baseline_anomaly_intensity": scored["baseline_anomaly_intensity"].to_numpy(dtype=float),
            "behavioral_anomaly_intensity": scored["behavioral_anomaly_intensity"].to_numpy(dtype=float),
            "rule_score_context": scored["rule_score_context"].to_numpy(dtype=float),
            "alert": scored["alert"].to_numpy(dtype=bool),
        })
        checkpoint_path = destination / f"step_{step:04d}.csv"
        _atomic_csv(checkpoint_path, checkpoint)
        manifest["checkpoint_files"].append(checkpoint_path.name)
        manifest["last_completed_step"] = step
        _atomic_json(manifest_path, manifest)
        row_id += len(checkpoint)
        seen_steps.append(step)
    manifest["resumed_steps"] = [min(seen_steps), max(seen_steps)] if seen_steps else []
    _atomic_json(manifest_path, manifest)
    return manifest


def combine_and_validate(recovery_dir: str | Path, *, expected_rows: int = EXPECTED_TOTAL_ROWS, raw_path: str | Path | None = None) -> pd.DataFrame:
    """Combine immutable prefix and complete step checkpoints only after validation."""

    destination = Path(recovery_dir)
    prefix = pd.read_csv(destination / "preserved_prefix_scores.csv")
    checkpoints = sorted(destination.glob("step_*.csv"))
    suffix = pd.concat((pd.read_csv(path) for path in checkpoints), ignore_index=True) if checkpoints else pd.DataFrame()
    complete = pd.concat([prefix, suffix], ignore_index=True)
    if len(complete) != expected_rows:
        raise ValueError(f"Incomplete combined cache: {len(complete)} != {expected_rows}")
    if not np.array_equal(complete["row_id"].to_numpy(), np.arange(expected_rows)):
        raise ValueError("Combined row IDs are not unique and sequential")
    if complete["step"].tolist() != sorted(complete["step"].tolist()) or set(complete["step"]) != set(range(378, 744)):
        raise ValueError("Combined steps are incomplete or unordered")
    if not complete["isFraud"].isin([0, 1]).all():
        raise ValueError("Combined labels are not binary")
    if not np.isfinite(complete[list(PREFIX_COLUMNS[3:7])].to_numpy(dtype=float)).all():
        raise ValueError("Combined scores contain non-finite values")
    if raw_path is not None:
        cursor = 0
        for source_step in iter_complete_steps(str(raw_path), chunksize=100_000, include_target=True):
            step = int(source_step["step"].iloc[0])
            if step < 378:
                continue
            if step > 743:
                break
            observed = complete.iloc[cursor:cursor + len(source_step)]
            if len(observed) != len(source_step) or not np.array_equal(observed["step"].to_numpy(), source_step["step"].to_numpy()) or not np.array_equal(observed["isFraud"].to_numpy(), source_step["isFraud"].to_numpy()):
                raise ValueError(f"Combined cache source alignment failed at step {step}")
            cursor += len(source_step)
        if cursor != expected_rows:
            raise ValueError(f"Combined cache source row count mismatch: {cursor} != {expected_rows}")
    output = destination / "complete_holdout_scores.csv"
    if output.exists():
        raise FileExistsError(output)
    _atomic_csv(output, complete)
    return complete


def verify_real_model_boundary(
    raw_path: str | Path,
    *,
    model_paths: dict[str, Path],
    prefix_path: str | Path | None = None,
    boundary_step: int = PREFIX_END_STEP + 1,
    sample_size: int = 32,
) -> dict[str, Any]:
    """Reconstruct history once and score a deterministic boundary sample.

    Chunk-boundary invariance is covered by fixture tests. This real-data check
    validates one frozen model state and deliberately does not claim to prove
    every aspect of historical-state reconstruction independently.
    """

    if sample_size < 1:
        raise ValueError("sample_size must be positive")
    started = time.perf_counter()
    tracemalloc.start()
    assessor = FinalRiskAssessment.from_joblib_paths(
        supervised_path=model_paths["supervised"],
        baseline_anomaly_path=model_paths["baseline_anomaly"],
        behavioral_anomaly_path=model_paths["behavioral_anomaly"],
    )
    boundary_result: pd.DataFrame | None = None
    prefix_result: pd.DataFrame | None = None
    prefix_differences: dict[str, float] | None = None
    if prefix_path is not None:
        prefix = pd.read_csv(prefix_path)
        prefix_result = prefix.loc[prefix["step"] == PREFIX_END_STEP].reset_index(drop=True)
        if len(prefix_result) != 2792:
            raise ValueError(f"Unexpected step-428 prefix rows: {len(prefix_result)}")
    checkpoints: list[dict[str, Any]] = []
    process_memory = ctypes.WinDLL("Psapi.dll")
    class _MemoryCounters(ctypes.Structure):
        _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD), ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t)]
    process_memory.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(_MemoryCounters), wintypes.DWORD]
    process_memory.GetProcessMemoryInfo.restype = wintypes.BOOL
    def rss_mb() -> float:
        counters = _MemoryCounters(); counters.cb = ctypes.sizeof(counters)
        process_memory.GetProcessMemoryInfo(ctypes.windll.kernel32.GetCurrentProcess(), ctypes.byref(counters), counters.cb)
        return counters.WorkingSetSize / (1024 * 1024)
    history_steps = 0
    for step_frame in iter_complete_steps(str(raw_path), chunksize=100_000, include_target=True):
        step = int(step_frame["step"].iloc[0])
        if step < boundary_step:
            if step == PREFIX_END_STEP and prefix_result is not None:
                regenerated = assessor.assess_step(step_frame).reset_index(drop=True)
                columns = ["fraud_probability", "baseline_anomaly_intensity", "behavioral_anomaly_intensity", "rule_score_context", "alert"]
                prefix_differences = compare_persisted_scores(
                    regenerated, prefix_result,
                    expected_steps=step_frame["step"].to_numpy(),
                    expected_labels=step_frame["isFraud"].to_numpy(),
                )
            else:
                assessor.process_history_state_only(step_frame)
            history_steps += 1
            if step % 50 == 0:
                checkpoints.append({"step": step, "elapsed_seconds": time.perf_counter() - started, "rss_mb": rss_mb()})
            continue
        if step != boundary_step:
            raise ValueError(f"Boundary step {boundary_step} was not reached")
        boundary_result = assessor.assess_step(step_frame).reset_index(drop=True)
        break
    if boundary_result is None:
        raise ValueError("No boundary scores were produced")
    sample_indices = np.linspace(0, len(boundary_result) - 1, min(sample_size, len(boundary_result)), dtype=int)
    sample = boundary_result.iloc[sample_indices]
    score_columns = [
        "fraud_probability", "baseline_anomaly_intensity",
        "behavioral_anomaly_intensity", "rule_score_context",
    ]
    if not np.isfinite(sample[score_columns].to_numpy(dtype=float)).all():
        raise ValueError("Boundary sample contains non-finite scores")
    if not np.array_equal(sample["alert"].to_numpy(), (sample["fraud_probability"].to_numpy() >= CALIBRATED_RF_ALERT_THRESHOLD)):
        raise ValueError("Boundary alerts are not derived solely from frozen RF probability")
    _, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return {
        "boundary_step": boundary_step,
        "rows": len(boundary_result),
        "sample_rows": len(sample),
        "sample_indices": sample_indices.tolist(),
        "history_steps_reconstructed": history_steps,
        "checkpoints": checkpoints,
        "prefix_step_428_rows": len(prefix_result) if prefix_result is not None else None,
        "prefix_step_428_max_differences": prefix_differences,
        "independent_replay": False,
        "limitation": "Single reconstructed state; chunk invariance remains fixture-tested and source alignment remains independently checked.",
        "runtime_seconds": time.perf_counter() - started,
        "python_peak_memory_mb": peak_bytes / (1024 * 1024),
        "equivalent": True,
    }


def calculate_metrics(frame: pd.DataFrame, threshold: float = CALIBRATED_RF_ALERT_THRESHOLD) -> dict[str, Any]:
    """Calculate metrics only from an integrity-validated complete cache."""

    labels = frame["isFraud"].to_numpy(dtype=int)
    scores = frame["fraud_probability"].to_numpy(dtype=float)
    predicted = scores >= threshold
    tn, fp, fn, tp = confusion_matrix(labels, predicted, labels=[0, 1]).ravel()
    order = np.argsort(-scores, kind="stable")
    fraud_total = int(labels.sum())
    budgets = {}
    for budget in (10, 50, 100, 500, 1000, 5000):
        selected = order[:min(budget, len(order))]
        captured = int(labels[selected].sum())
        budgets[str(budget)] = {"alerts": len(selected), "fraud_captured": captured, "false_positives": len(selected) - captured, "precision": float(captured / len(selected)) if len(selected) else 0.0, "recall": float(captured / fraud_total) if fraud_total else 0.0}
    return {
        "rows": len(frame), "fraud_count": int(labels.sum()),
        "average_precision": float(average_precision_score(labels, scores)),
        "roc_auc": float(roc_auc_score(labels, scores)),
        "precision": float(precision_score(labels, predicted, zero_division=0)),
        "recall": float(recall_score(labels, predicted, zero_division=0)),
        "f1": float(f1_score(labels, predicted, zero_division=0)),
        "true_positives": int(tp), "false_positives": int(fp),
        "false_negatives": int(fn), "true_negatives": int(tn), "alert_budgets": budgets,
    }


__all__ = [
    "EXPECTED_TOTAL_ROWS", "HOLDOUT_END_STEP", "PREFIX_END_STEP", "RECOVERY_VERSION", "PERSISTED_SCORE_ATOL",
    "calculate_metrics", "combine_and_validate", "compare_persisted_scores", "initialize_recovery",
    "resume_suffix", "verify_frozen_inputs", "verify_prefix_cache", "verify_real_model_boundary",
]
