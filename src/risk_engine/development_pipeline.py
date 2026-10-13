"""Versioned, single-pass Module 4 development scoring pipeline.

The pipeline deliberately separates transaction scoring from calibration and
fusion.  A chronological pass writes one aligned component-score cache; later
fusion configurations consume that cache without rebuilding history or
calling a model again.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from src.risk_engine.behavioral_state import ChronologicalBehavioralProcessor, iter_complete_steps
from src.risk_engine.decisions import RiskDecisionPolicy, make_risk_decisions
from src.risk_engine.fusion import FusionWeights, RiskScoreFusion
from src.risk_engine.normalization import EmpiricalCdfNormalizer
from src.risk_engine.rules import evaluate_paysim_rules
from src.risk_engine.scorers import IsolationForestScorer, SupervisedFraudScorer


MODULE4_VERSION = "module4_v1"
CALIBRATION_START_STEP = 46
CALIBRATION_END_STEP = 200
DEVELOPMENT_EVAL_START_STEP = 201
DEVELOPMENT_EVAL_END_STEP = 377
FINAL_HOLDOUT_START_STEP = 378

CACHE_COLUMNS = (
    "row_id",
    "step",
    "isFraud",
    "supervised_score",
    "anomaly_baseline_raw",
    "anomaly_behavioral_raw",
    "rule_score",
    "rule_reasons_json",
)


@dataclass(frozen=True)
class DevelopmentSplit:
    """Fixed step boundaries for the versioned development experiment."""

    calibration_start: int = CALIBRATION_START_STEP
    calibration_end: int = CALIBRATION_END_STEP
    evaluation_start: int = DEVELOPMENT_EVAL_START_STEP
    evaluation_end: int = DEVELOPMENT_EVAL_END_STEP

    def __post_init__(self) -> None:
        if not (
            self.calibration_start <= self.calibration_end
            < self.evaluation_start
            <= self.evaluation_end
            < FINAL_HOLDOUT_START_STEP
        ):
            raise ValueError("Development split must end before the untouched holdout")


@dataclass(frozen=True)
class CalibrationResult:
    """Frozen calibration parameters and their provenance."""

    weights: FusionWeights
    alert_threshold: float
    medium_threshold: float
    calibration_start: int
    calibration_end: int
    selected_by: str


DEFAULT_WEIGHT_CANDIDATES = (
    FusionWeights(supervised=1.0),
    FusionWeights(supervised=1.0, anomaly_baseline=1.0),
    FusionWeights(supervised=1.0, anomaly_behavioral=1.0),
    FusionWeights(supervised=1.0, anomaly_baseline=1.0, anomaly_behavioral=1.0),
    FusionWeights(supervised=1.0, rules=1.0),
    FusionWeights(supervised=1.0, anomaly_baseline=1.0, anomaly_behavioral=1.0, rules=1.0),
)


def _require_cache_columns(frame: pd.DataFrame) -> None:
    missing = sorted(set(CACHE_COLUMNS).difference(frame.columns))
    if missing:
        raise ValueError(f"Score cache is missing columns: {missing}")


def score_development_to_csv(
    csv_path: str | Path,
    output_path: str | Path,
    *,
    supervised_model: object,
    baseline_model: object,
    behavioral_model: object,
    chunksize: int = 100_000,
    split: DevelopmentSplit = DevelopmentSplit(),
    overwrite: bool = False,
) -> dict[str, object]:
    """Score steps 46–377 exactly once and persist an aligned component cache.

    The processor consumes all earlier steps to establish history, but only
    steps in the approved development interval are scored and written.  The
    writer uses append mode per complete simulation step, keeping peak output
    memory bounded by one step plus the processor's historical dictionaries.
    """

    destination = Path(output_path)
    if destination.exists() and not overwrite:
        raise FileExistsError(f"Refusing to overwrite existing cache: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)

    supervised = SupervisedFraudScorer(supervised_model)
    baseline = IsolationForestScorer(baseline_model, ("amount", "oldbalanceOrg", "oldbalanceDest", "step"))
    behavioral = IsolationForestScorer(
        behavioral_model,
        ("amount", "oldbalanceOrg", "oldbalanceDest", "step", "sender_txn_count_prior", "sender_velocity_3_steps_prior", "sender_avg_amount_prior", "sender_amount_ratio_to_avg_prior", "sender_same_type_count_prior", "sender_same_type_share_prior", "receiver_txn_count_prior", "receiver_avg_amount_prior", "receiver_amount_ratio_to_avg_prior"),
    )
    processor = ChronologicalBehavioralProcessor()
    row_id = 0
    rows_written = 0
    header_written = False
    for step_frame in iter_complete_steps(str(csv_path), chunksize=chunksize, include_target=True):
        step = int(step_frame["step"].iloc[0])
        if step > split.evaluation_end:
            break
        featured = processor.process_step(step_frame)
        if step < split.calibration_start:
            continue
        supervised_scores = supervised.score(featured)
        baseline_scores = baseline.score(featured)
        behavioral_scores = behavioral.score(featured)
        rule_scores, rule_reasons = evaluate_paysim_rules(featured, behavioral=featured)
        labels = featured["isFraud"].to_numpy(dtype="int8") if "isFraud" in featured else np.full(len(featured), -1, dtype="int8")
        result = pd.DataFrame(
            {
                "row_id": np.arange(row_id, row_id + len(featured), dtype="int64"),
                "step": featured["step"].to_numpy(dtype="int16"),
                "isFraud": labels,
                "supervised_score": supervised_scores,
                "anomaly_baseline_raw": baseline_scores,
                "anomaly_behavioral_raw": behavioral_scores,
                "rule_score": rule_scores,
                "rule_reasons_json": [json.dumps(reasons, sort_keys=True) for reasons in rule_reasons],
            }
        )
        result.to_csv(destination, mode="w" if not header_written else "a", header=not header_written, index=False)
        header_written = True
        row_id += len(result)
        rows_written += len(result)
    if not header_written:
        raise ValueError("No transactions were scored in the requested development range")
    return {
        "version": MODULE4_VERSION,
        "rows_written": rows_written,
        "first_step": split.calibration_start,
        "last_step": split.evaluation_end,
        "cache_columns": list(CACHE_COLUMNS),
        "history_processed_through_step": split.calibration_start - 1,
        "final_holdout_start_step": FINAL_HOLDOUT_START_STEP,
    }


def load_score_cache(path: str | Path) -> pd.DataFrame:
    """Load and validate the aligned score cache without changing its order."""

    frame = pd.read_csv(path)
    _require_cache_columns(frame)
    if not frame["row_id"].is_monotonic_increasing or frame["row_id"].duplicated().any():
        raise ValueError("Score cache row_id must be unique and ordered")
    for column in CACHE_COLUMNS[3:7]:
        if not np.isfinite(frame[column].to_numpy(dtype=float)).all():
            raise ValueError(f"Score cache contains non-finite values: {column}")
    return frame


def _normalization_inputs(cache: pd.DataFrame) -> tuple[EmpiricalCdfNormalizer, EmpiricalCdfNormalizer]:
    return (
        EmpiricalCdfNormalizer().fit(cache["anomaly_baseline_raw"].to_numpy()),
        EmpiricalCdfNormalizer().fit(cache["anomaly_behavioral_raw"].to_numpy()),
    )


def fit_calibration_normalizers(
    calibration_cache: pd.DataFrame,
    *,
    split: DevelopmentSplit = DevelopmentSplit(),
) -> tuple[EmpiricalCdfNormalizer, EmpiricalCdfNormalizer]:
    """Fit anomaly normalizers from calibration rows only."""

    _require_cache_columns(calibration_cache)
    if calibration_cache.empty:
        raise ValueError("Calibration cache cannot be empty")
    if not calibration_cache["step"].between(split.calibration_start, split.calibration_end).all():
        raise ValueError("Calibration cache contains rows outside calibration steps")
    return _normalization_inputs(calibration_cache)


def _best_f1_threshold(scores: np.ndarray, labels: np.ndarray) -> tuple[float, float]:
    """Scan sorted cumulative counts, preserving lowest-threshold F1 ties.

    Sorting costs O(n log n); tied scores are evaluated together using the
    same >= decision rule as inference. Endpoints 0 and 1 remain candidates.
    """
    order = np.argsort(scores, kind="stable")
    sorted_scores = scores[order]
    positives = np.concatenate(([0], np.cumsum(labels[order], dtype=np.int64)))
    thresholds = np.unique(np.concatenate(([0.0, 1.0], sorted_scores)))
    positions = np.searchsorted(sorted_scores, thresholds, side="left")
    true_positives = positives[-1] - positives[positions]
    denominator = len(scores) - positions + positives[-1]
    f1 = np.divide(2.0 * true_positives, denominator,
                   out=np.zeros(len(thresholds)), where=denominator != 0)
    best = int(np.argmax(f1))
    return float(thresholds[best]), float(f1[best])


def fit_fusion_weights(
    calibration_cache: pd.DataFrame,
    *,
    candidates: tuple[FusionWeights, ...] = DEFAULT_WEIGHT_CANDIDATES,
    split: DevelopmentSplit = DevelopmentSplit(),
) -> FusionWeights:
    """Select weights from a fixed candidate set using calibration rows only."""

    _require_cache_columns(calibration_cache)
    if calibration_cache.empty or not calibration_cache["isFraud"].isin([0, 1]).all():
        raise ValueError("Calibration cache must contain binary labels")
    if not candidates:
        raise ValueError("At least one fusion-weight candidate is required")
    baseline_normalizer, behavioral_normalizer = fit_calibration_normalizers(calibration_cache, split=split)
    baseline = baseline_normalizer.transform(calibration_cache["anomaly_baseline_raw"].to_numpy())
    behavioral = behavioral_normalizer.transform(calibration_cache["anomaly_behavioral_raw"].to_numpy())
    labels = calibration_cache["isFraud"].to_numpy(dtype=int)
    best_weights = candidates[0]
    best_key = (-1.0, -1.0, 0)
    for position, candidate in enumerate(candidates):
        fused = RiskScoreFusion(candidate).combine(
            supervised=calibration_cache["supervised_score"].to_numpy(),
            anomaly_baseline=baseline,
            anomaly_behavioral=behavioral,
            rules=calibration_cache["rule_score"].to_numpy(),
        )
        _, candidate_best_f1 = _best_f1_threshold(fused, labels)
        key = (candidate_best_f1, -sum((candidate.anomaly_baseline, candidate.anomaly_behavioral, candidate.rules)), -position)
        if key > best_key:
            best_key = key
            best_weights = candidate
    return best_weights


def calibrate_fusion(
    calibration_cache: pd.DataFrame,
    *,
    weights: FusionWeights | None = None,
    candidates: tuple[FusionWeights, ...] = DEFAULT_WEIGHT_CANDIDATES,
    split: DevelopmentSplit = DevelopmentSplit(),
) -> CalibrationResult:
    """Fit normalization and a validation-only alert threshold.

    Explicit weights are preserved; otherwise the fixed candidate set is
    searched using calibration labels only.
    """

    _require_cache_columns(calibration_cache)
    if calibration_cache.empty or not calibration_cache["step"].between(split.calibration_start, split.calibration_end).all():
        raise ValueError("Calibration cache contains rows outside calibration steps")
    if weights is None:
        weights = fit_fusion_weights(calibration_cache, candidates=candidates, split=split)
    baseline_normalizer, behavioral_normalizer = fit_calibration_normalizers(calibration_cache, split=split)
    normalized_baseline = baseline_normalizer.transform(calibration_cache["anomaly_baseline_raw"].to_numpy())
    normalized_behavioral = behavioral_normalizer.transform(calibration_cache["anomaly_behavioral_raw"].to_numpy())
    fused = RiskScoreFusion(weights).combine(
        supervised=calibration_cache["supervised_score"].to_numpy(),
        anomaly_baseline=normalized_baseline,
        anomaly_behavioral=normalized_behavioral,
        rules=calibration_cache["rule_score"].to_numpy(),
    )
    if not calibration_cache["isFraud"].isin([0, 1]).all():
        raise ValueError("Calibration cache must contain binary isFraud labels")
    labels = calibration_cache["isFraud"].to_numpy(dtype=int)
    best = _best_f1_threshold(fused, labels)
    return CalibrationResult(
        weights=weights,
        alert_threshold=best[0],
        medium_threshold=min(0.5, best[0]),
        calibration_start=split.calibration_start,
        calibration_end=split.calibration_end,
        selected_by="maximum calibration F1; anomaly CDFs fitted on calibration rows",
    )


def apply_calibration(
    cache: pd.DataFrame,
    calibration: CalibrationResult,
    *,
    normalizers: tuple[EmpiricalCdfNormalizer, EmpiricalCdfNormalizer],
) -> pd.DataFrame:
    """Apply frozen parameters and return deterministic decisions/explanations."""

    _require_cache_columns(cache)
    baseline_normalizer, behavioral_normalizer = normalizers
    baseline = baseline_normalizer.transform(cache["anomaly_baseline_raw"].to_numpy())
    behavioral = behavioral_normalizer.transform(cache["anomaly_behavioral_raw"].to_numpy())
    fused = RiskScoreFusion(calibration.weights).combine(
        supervised=cache["supervised_score"].to_numpy(),
        anomaly_baseline=baseline,
        anomaly_behavioral=behavioral,
        rules=cache["rule_score"].to_numpy(),
    )
    reasons = [json.loads(value) for value in cache["rule_reasons_json"]]
    decisions = make_risk_decisions(
        fused,
        policy=RiskDecisionPolicy(
            alert_threshold=calibration.alert_threshold,
            high_threshold=calibration.alert_threshold,
            medium_threshold=calibration.medium_threshold,
        ),
        component_scores={
            "supervised": cache["supervised_score"].to_numpy(),
            "anomaly_baseline": baseline,
            "anomaly_behavioral": behavioral,
            "rules": cache["rule_score"].to_numpy(),
        },
        rule_reasons=reasons,
    )
    decisions["explanations"] = decisions["explanations"].map(
        lambda values: values if values else ["no_elevated_contributing_signal_identified"]
    )
    return decisions


__all__ = [
    "CALIBRATION_END_STEP",
    "CALIBRATION_START_STEP",
    "CACHE_COLUMNS",
    "CalibrationResult",
    "DEVELOPMENT_EVAL_END_STEP",
    "DEVELOPMENT_EVAL_START_STEP",
    "DevelopmentSplit",
    "MODULE4_VERSION",
    "apply_calibration",
    "calibrate_fusion",
    "fit_calibration_normalizers",
    "fit_fusion_weights",
    "load_score_cache",
    "score_development_to_csv",
]
