"""Single, frozen temporal holdout evaluation for Module 4 Stage 4."""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, confusion_matrix, f1_score, precision_score, recall_score, roc_auc_score

from src.risk_engine.behavioral_state import iter_complete_steps
from src.risk_engine.final_architecture import (
    CALIBRATED_RF_ALERT_THRESHOLD,
    FINAL_ARCHITECTURE_VERSION,
    FinalRiskAssessment,
    FinalRiskAssessmentConfig,
)


ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data/raw/PS_20174392719_1491204439457_log.csv"
OUT = ROOT / "artifacts/module4_final_holdout_v1"
SCORES = OUT / "holdout_scores.csv"
START_STEP = 378
END_STEP = 743
HISTORY_END_STEP = 377


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _metrics(frame: pd.DataFrame, threshold: float) -> dict[str, object]:
    labels = frame["isFraud"].to_numpy(dtype=int)
    scores = frame["fraud_probability"].to_numpy(dtype=float)
    predicted = scores >= threshold
    tn, fp, fn, tp = confusion_matrix(labels, predicted, labels=[0, 1]).ravel()
    order = np.argsort(-scores, kind="stable")
    budgets: dict[str, dict[str, int | float]] = {}
    fraud_total = int(labels.sum())
    for budget in (10, 50, 100, 500, 1000, 5000):
        selected = order[: min(budget, len(order))]
        captured = int(labels[selected].sum())
        alerts = int(len(selected))
        budgets[str(budget)] = {
            "alerts": alerts,
            "fraud_captured": captured,
            "false_positives": alerts - captured,
            "precision": float(captured / alerts) if alerts else 0.0,
            "recall": float(captured / fraud_total) if fraud_total else 0.0,
        }
    return {
        "total_transactions": int(len(frame)),
        "fraud_count": fraud_total,
        "fraud_rate": float(fraud_total / len(frame)),
        "average_precision": float(average_precision_score(labels, scores)),
        "roc_auc": float(roc_auc_score(labels, scores)),
        "threshold": threshold,
        "precision": float(precision_score(labels, predicted, zero_division=0)),
        "recall": float(recall_score(labels, predicted, zero_division=0)),
        "f1": float(f1_score(labels, predicted, zero_division=0)),
        "true_positives": int(tp),
        "false_positives": int(fp),
        "false_negatives": int(fn),
        "true_negatives": int(tn),
        "alert_count": int(predicted.sum()),
        "alert_budgets": budgets,
    }


def main() -> None:
    if not RAW.exists():
        raise FileNotFoundError(RAW)
    if OUT.exists():
        raise FileExistsError(f"Refusing to overwrite final holdout artifact directory: {OUT}")
    OUT.mkdir(parents=True)
    started = time.perf_counter()
    model_paths = {
        "supervised": ROOT / "artifacts/paysim_v2/random_forest.joblib",
        "baseline_anomaly": ROOT / "artifacts/anomaly_detection_behavioral_1m/isolation_forest_baseline_matched.joblib",
        "behavioral_anomaly": ROOT / "artifacts/anomaly_detection_behavioral_1m/isolation_forest_behavioral.joblib",
    }
    assessor = FinalRiskAssessment.from_joblib_paths(
        model_paths["supervised"],
        model_paths["baseline_anomaly"],
        model_paths["behavioral_anomaly"],
    )
    header = True
    output_rows = 0
    steps_seen = []
    row_id = 0
    for step_frame in iter_complete_steps(str(RAW), chunksize=100_000, include_target=True):
        step = int(step_frame["step"].iloc[0])
        if step > END_STEP:
            break
        assessment = assessor.assess_step(step_frame)
        if step < START_STEP:
            if step > HISTORY_END_STEP:
                raise RuntimeError("Unexpected step gap before holdout")
            continue
        if step <= HISTORY_END_STEP:
            raise RuntimeError("Holdout boundary was not respected")
        steps_seen.append(step)
        result = pd.DataFrame(
            {
                "row_id": np.arange(row_id, row_id + len(step_frame), dtype="int64"),
                "step": step_frame["step"].to_numpy(dtype="int16"),
                "isFraud": step_frame["isFraud"].to_numpy(dtype="int8"),
                "fraud_probability": assessment["fraud_probability"].to_numpy(dtype=float),
                "baseline_anomaly_intensity": assessment["baseline_anomaly_intensity"].to_numpy(dtype=float),
                "behavioral_anomaly_intensity": assessment["behavioral_anomaly_intensity"].to_numpy(dtype=float),
                "rule_score_context": assessment["rule_score_context"].to_numpy(dtype=float),
                "alert": assessment["alert"].to_numpy(dtype=bool),
            }
        )
        result.to_csv(SCORES, mode="w" if header else "a", header=header, index=False)
        header = False
        row_id += len(result)
        output_rows += len(result)
    if not steps_seen or steps_seen[0] != START_STEP or steps_seen[-1] != END_STEP:
        raise RuntimeError(f"Incomplete holdout steps: {steps_seen[:1]}..{steps_seen[-1:]}")
    scores = pd.read_csv(SCORES)
    metrics = _metrics(scores, CALIBRATED_RF_ALERT_THRESHOLD)
    dev_path = ROOT / "artifacts/module4_development_v1/development_results_v3.json"
    dev = json.loads(dev_path.read_text(encoding="utf-8"))
    dev_rf = dev["results"]["random_forest_only"]["metrics"]
    report = {
        "version": "module4_final_holdout_v1",
        "architecture_version": FINAL_ARCHITECTURE_VERSION,
        "calibration_steps": [46, 200],
        "history_processed_through_step": HISTORY_END_STEP,
        "holdout_steps": [START_STEP, END_STEP],
        "holdout_steps_seen": [int(min(steps_seen)), int(max(steps_seen)), len(set(steps_seen))],
        "final_holdout_accessed": True,
        "threshold": CALIBRATED_RF_ALERT_THRESHOLD,
        "threshold_provenance": "Frozen maximum-F1 threshold from steps 46-200; no holdout tuning",
        "selection_policy": "Random Forest probability alone determines ranking and alert decisions; anomaly intensities and rules are contextual indicators only.",
        "model_artifact_sha256": {name: _sha256(path) for name, path in model_paths.items()},
        "scores_path": str(SCORES.relative_to(ROOT)),
        "output_rows": output_rows,
        "metrics": metrics,
        "development_comparison": {
            "evaluation_steps": dev["evaluation_steps"],
            "total_transactions": dev["evaluation_rows"],
            "fraud_count": dev["evaluation_fraud_count"],
            "fraud_rate": dev["evaluation_fraud_count"] / dev["evaluation_rows"],
            "average_precision": dev_rf["average_precision"],
            "roc_auc": dev_rf["roc_auc"],
            "precision": dev_rf["precision_at_calibrated_threshold"],
            "recall": dev_rf["recall_at_calibrated_threshold"],
            "f1": 2 * dev_rf["precision_at_calibrated_threshold"] * dev_rf["recall_at_calibrated_threshold"] / (dev_rf["precision_at_calibrated_threshold"] + dev_rf["recall_at_calibrated_threshold"]),
        },
        "runtime_seconds": round(time.perf_counter() - started, 2),
        "memory_measurement_note": "Peak working-set observation is recorded from the active process externally when the evaluator runs; no architecture or model changes are made.",
    }
    destination = OUT / "final_holdout_results.json"
    destination.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
