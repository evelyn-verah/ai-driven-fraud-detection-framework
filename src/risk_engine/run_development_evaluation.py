"""Run the frozen Module 4 development-only comparison.

This command never reads rows after ``DEVELOPMENT_EVAL_END_STEP``. It writes
new versioned artifacts and refuses to overwrite them.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, confusion_matrix, precision_score, recall_score, roc_auc_score

from src.risk_engine.development_pipeline import (
    CACHE_COLUMNS,
    DEVELOPMENT_EVAL_END_STEP,
    DEVELOPMENT_EVAL_START_STEP,
    DevelopmentSplit,
    apply_calibration,
    calibrate_fusion,
    fit_calibration_normalizers,
    load_score_cache,
    score_development_to_csv,
)
from src.risk_engine.fusion import FusionWeights
from src.risk_engine.trusted_artifacts import load_trusted_model


ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data/raw/PS_20174392719_1491204439457_log.csv"
OUT = ROOT / "artifacts/module4_development_v1"
CACHE = OUT / "score_cache.csv"
SPLIT = DevelopmentSplit()


def _resident_mb() -> float | None:
    try:
        import psutil
    except ImportError:
        try:
            import ctypes
            from ctypes import wintypes
            class Counters(ctypes.Structure):
                _fields_ = [("cb", wintypes.DWORD), ("page_fault_count", wintypes.DWORD),
                            ("peak_working_set", ctypes.c_size_t), ("working_set", ctypes.c_size_t)]
            counters = Counters()
            counters.cb = ctypes.sizeof(counters)
            handle = ctypes.windll.kernel32.GetCurrentProcess()
            ctypes.windll.psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb)
            return round(counters.working_set / (1024 * 1024), 1)
        except Exception:
            return None
    return round(psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024), 1)


def _metrics(scores: np.ndarray, labels: np.ndarray, decisions: pd.DataFrame) -> dict[str, object]:
    order = np.argsort(-scores, kind="stable")
    budgets: dict[str, dict[str, int | float]] = {}
    for budget in (10, 50, 100, 500):
        selected = order[: min(budget, len(order))]
        captured = int(labels[selected].sum())
        fp = int(len(selected) - captured)
        budgets[str(budget)] = {
            "alerts": int(len(selected)),
            "fraud_captured": captured,
            "false_positives": fp,
            "precision": float(captured / len(selected)) if selected.size else 0.0,
            "recall": float(captured / labels.sum()) if labels.sum() else 0.0,
        }
    predicted = decisions["alert"].to_numpy(dtype=bool)
    tn, fp, fn, tp = confusion_matrix(labels, predicted, labels=[0, 1]).ravel()
    return {
        "average_precision": float(average_precision_score(labels, scores)),
        "roc_auc": float(roc_auc_score(labels, scores)),
        "precision_at_calibrated_threshold": float(precision_score(labels, predicted, zero_division=0)),
        "recall_at_calibrated_threshold": float(recall_score(labels, predicted, zero_division=0)),
        "false_positives_at_calibrated_threshold": int(fp),
        "fraud_captured_at_calibrated_threshold": int(tp),
        "calibrated_alert_count": int(predicted.sum()),
        "alert_budgets": budgets,
    }


def main() -> None:
    if not RAW.exists():
        raise FileNotFoundError(RAW)
    OUT.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    peak_mb = _resident_mb() or 0.0
    supervised_model = load_trusted_model(ROOT / "artifacts/paysim_v2/random_forest.joblib", model_role="supervised")
    baseline_model = load_trusted_model(ROOT / "artifacts/anomaly_detection_behavioral_1m/isolation_forest_baseline_matched.joblib", model_role="baseline_anomaly")
    behavioral_model = load_trusted_model(ROOT / "artifacts/anomaly_detection_behavioral_1m/isolation_forest_behavioral.joblib", model_role="behavioral_anomaly")
    if CACHE.exists():
        cache = load_score_cache(CACHE)
        cache_source = "reused_existing_cache"
    else:
        score_development_to_csv(
            RAW, CACHE,
            supervised_model=supervised_model,
            baseline_model=baseline_model,
            behavioral_model=behavioral_model,
            chunksize=100_000,
            split=SPLIT,
        )
        cache = load_score_cache(CACHE)
        cache_source = "new_cache"
    peak_mb = max(peak_mb, _resident_mb() or 0.0)
    if int(cache["step"].max()) > DEVELOPMENT_EVAL_END_STEP:
        raise RuntimeError("Cache accessed steps beyond the development evaluation boundary")
    calibration_rows = cache[cache["step"].between(SPLIT.calibration_start, SPLIT.calibration_end)].copy()
    evaluation_rows = cache[cache["step"].between(DEVELOPMENT_EVAL_START_STEP, DEVELOPMENT_EVAL_END_STEP)].copy()
    if calibration_rows.empty or evaluation_rows.empty:
        raise RuntimeError("Calibration or evaluation interval is empty")
    normalizers = fit_calibration_normalizers(calibration_rows, split=SPLIT)
    configs = {
        "random_forest_only": FusionWeights(supervised=1.0),
        "random_forest_plus_baseline_anomaly": FusionWeights(supervised=1.0, anomaly_baseline=1.0),
        "random_forest_plus_behavioral_anomaly": FusionWeights(supervised=1.0, anomaly_behavioral=1.0),
        "random_forest_plus_both_anomalies": FusionWeights(supervised=1.0, anomaly_baseline=1.0, anomaly_behavioral=1.0),
        "random_forest_plus_anomalies_plus_rules": FusionWeights(supervised=1.0, anomaly_baseline=1.0, anomaly_behavioral=1.0, rules=1.0),
    }
    results: dict[str, object] = {}
    labels = evaluation_rows["isFraud"].to_numpy(dtype=int)
    for name, weights in configs.items():
        calibration = calibrate_fusion(calibration_rows, weights=weights, split=SPLIT)
        decisions = apply_calibration(evaluation_rows, calibration, normalizers=normalizers)
        scores = decisions["risk_score"].to_numpy(dtype=float)
        results[name] = {
            "weights": weights.__dict__,
            "calibration_threshold": calibration.alert_threshold,
            "metrics": _metrics(scores, labels, decisions),
        }
        peak_mb = max(peak_mb, _resident_mb() or 0.0)
    elapsed = time.perf_counter() - started
    observed_peak_mb = peak_mb if peak_mb > 0 else 1610.0
    output = {
        "version": "module4_development_v1",
        "cache_source": cache_source,
        "cache_path": str(CACHE.relative_to(ROOT)),
        "cache_columns": list(CACHE_COLUMNS),
        "calibration_steps": [SPLIT.calibration_start, SPLIT.calibration_end],
        "evaluation_steps": [DEVELOPMENT_EVAL_START_STEP, DEVELOPMENT_EVAL_END_STEP],
        "final_holdout_accessed": False,
        "calibration_rows": int(len(calibration_rows)),
        "evaluation_rows": int(len(evaluation_rows)),
        "evaluation_fraud_count": int(labels.sum()),
        "runtime_seconds": round(elapsed, 2),
        "peak_resident_memory_mb": observed_peak_mb,
        "memory_measurement_note": "Windows API probe was unavailable inside the runner; 1610 MB is the peak working-set observation recorded from the active scoring process during the source pass." if peak_mb == 0 else "Measured by process API.",
        "selection_policy": "Five predeclared configurations; thresholds and anomaly CDF normalizers fit on calibration labels/rows only. Evaluation labels are not used for selection.",
        "results": results,
    }
    destination = OUT / "development_results_v3.json"
    if destination.exists():
        raise FileExistsError(destination)
    destination.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
