"""Read-only descriptive data and prediction drift comparisons."""
from __future__ import annotations

from datetime import datetime, timezone
import numpy as np
import pandas as pd

from .contracts import MonitoringWindow, validate_windows
from .engine import (
    ANOMALY_FIELDS,
    FROZEN_THRESHOLD,
    _validate_complete_windows,
    _validate_frame,
)

DRIFT_SCHEMA_VERSION = "module7_stage3_drift_v1"
PROBABILITY_BINS = np.linspace(0.0, 1.0, 11)
AMOUNT_BINS = np.array([0.0, 1.0, 10.0, 100.0, 1000.0, 10000.0, np.inf])
EPSILON = 1e-12


def _finite(values):
    series = pd.Series(pd.to_numeric(values, errors="coerce"), dtype=float)
    return series[np.isfinite(series.to_numpy(dtype=float))]


def ks_statistic(reference, comparison):
    """Return the two-sample empirical KS distance, or None if unavailable."""
    a = np.sort(_finite(reference).to_numpy(dtype=float))
    b = np.sort(_finite(comparison).to_numpy(dtype=float))
    if not len(a) or not len(b):
        return None
    points = np.sort(np.unique(np.concatenate([a, b])))
    cdf_a = np.searchsorted(a, points, side="right") / len(a)
    cdf_b = np.searchsorted(b, points, side="right") / len(b)
    return float(np.max(np.abs(cdf_a - cdf_b)))


def _histogram(values, bins):
    valid = _finite(values).to_numpy(dtype=float)
    if not len(valid):
        return np.zeros(len(bins) - 1, dtype=float)
    counts, _ = np.histogram(valid, bins=bins)
    return counts.astype(float)


def psi(reference, comparison, bins):
    """Population Stability Index with fixed bins and finite-value handling."""
    ref_counts = _histogram(reference, bins)
    cmp_counts = _histogram(comparison, bins)
    ref_total = ref_counts.sum()
    cmp_total = cmp_counts.sum()
    if not ref_total or not cmp_total:
        return None
    ref_share = np.maximum(ref_counts / ref_total, EPSILON)
    cmp_share = np.maximum(cmp_counts / cmp_total, EPSILON)
    return float(np.sum((cmp_share - ref_share) * np.log(cmp_share / ref_share)))


def _missingness(values):
    series = pd.to_numeric(values, errors="coerce")
    return {"count": int(len(series)), "missing_count": int(series.isna().sum()), "missing_rate": float(series.isna().mean()) if len(series) else 0.0}


def _continuous_metric(name, reference, comparison, bins):
    ref_missing = _missingness(reference)
    cmp_missing = _missingness(comparison)
    ref_hist = _histogram(reference, bins)
    cmp_hist = _histogram(comparison, bins)
    ref_total = ref_hist.sum()
    cmp_total = cmp_hist.sum()
    return {
        "feature": name,
        "metric_type": "continuous",
        "reference_count": ref_missing["count"] - ref_missing["missing_count"],
        "comparison_count": cmp_missing["count"] - cmp_missing["missing_count"],
        "ks_statistic": ks_statistic(reference, comparison),
        "psi": psi(reference, comparison, bins),
        "reference_missingness": ref_missing,
        "comparison_missingness": cmp_missing,
        "missingness_rate_change": float(cmp_missing["missing_rate"] - ref_missing["missing_rate"]),
        "fixed_bin_edges": [float(edge) if np.isfinite(edge) else "inf" for edge in bins],
        "reference_bin_proportions": (ref_hist / ref_total).tolist() if ref_total else [],
        "comparison_bin_proportions": (cmp_hist / cmp_total).tolist() if cmp_total else [],
        "interpretation": "Descriptive distribution comparison; not evidence of model degradation.",
    }


def _category_counts(values):
    series = pd.Series(values, dtype="object").where(pd.Series(values, dtype="object").notna(), "__MISSING__").map(str)
    return series.value_counts(dropna=False).to_dict()


def jensen_shannon(reference, comparison):
    """Jensen-Shannon divergence over the union of categorical levels."""
    a = _category_counts(reference)
    b = _category_counts(comparison)
    total_a, total_b = sum(a.values()), sum(b.values())
    if not total_a or not total_b:
        return None
    keys = sorted(set(a) | set(b))
    p = np.array([a.get(k, 0) / total_a for k in keys], dtype=float)
    q = np.array([b.get(k, 0) / total_b for k in keys], dtype=float)
    midpoint = (p + q) / 2.0
    p_safe = np.maximum(p, EPSILON)
    q_safe = np.maximum(q, EPSILON)
    m_safe = np.maximum(midpoint, EPSILON)
    value = 0.5 * np.sum(p_safe * np.log(p_safe / m_safe)) + 0.5 * np.sum(q_safe * np.log(q_safe / m_safe))
    return float(value)


def _categorical_metric(name, reference, comparison):
    ref = _category_counts(reference)
    cmp = _category_counts(comparison)
    keys = sorted(set(ref) | set(cmp))
    return {
        "feature": name,
        "metric_type": "categorical",
        "reference_count": int(sum(ref.values())),
        "comparison_count": int(sum(cmp.values())),
        "reference_levels": {key: int(ref.get(key, 0)) for key in keys},
        "comparison_levels": {key: int(cmp.get(key, 0)) for key in keys},
        "jensen_shannon_divergence": jensen_shannon(reference, comparison),
        "interpretation": "Descriptive categorical distribution comparison; levels absent from one window are retained as zero counts.",
    }


def _align_metadata(metadata, frame):
    if metadata is None:
        return None
    required = {"row_id", "step"}
    missing = required - set(metadata.columns)
    if missing:
        raise ValueError(f"metadata missing required columns: {sorted(missing)}")
    if metadata.row_id.duplicated().any():
        raise ValueError("duplicate metadata row_id")
    selected = metadata[metadata.row_id.isin(frame.row_id)].copy()
    score_steps = frame.set_index("row_id")["step"].sort_index().to_numpy()
    metadata_steps = selected.set_index("row_id")["step"].sort_index().to_numpy()
    if len(selected) != len(frame) or not np.array_equal(score_steps, metadata_steps):
        raise ValueError("metadata row_id/step alignment failure")
    return selected


def analyze_drift(
    frame,
    metadata,
    reference_window: MonitoringWindow,
    comparison_window: MonitoringWindow,
    expected_step_counts,
    source_artifacts=None,
    threshold=FROZEN_THRESHOLD,
):
    """Compare two ordered, complete, non-overlapping windows."""
    if reference_window.end_step >= comparison_window.start_step:
        raise ValueError("reference window must precede and not overlap comparison window")
    windows = validate_windows([reference_window, comparison_window])
    _validate_frame(frame, threshold)
    _validate_complete_windows(frame, windows, expected_step_counts)
    ref = frame[frame.step.between(reference_window.start_step, reference_window.end_step)].copy()
    cmp = frame[frame.step.between(comparison_window.start_step, comparison_window.end_step)].copy()
    ref_md = _align_metadata(metadata, ref)
    cmp_md = _align_metadata(metadata, cmp)

    continuous = {}
    if ref_md is not None and "amount" in ref_md.columns:
        amount = pd.to_numeric(ref_md["amount"], errors="coerce")
        if ((amount.dropna() < 0) | (~np.isfinite(amount.dropna()))).any():
            raise ValueError("metadata amount contains invalid values")
        cmp_amount = pd.to_numeric(cmp_md["amount"], errors="coerce")
        continuous["amount"] = _continuous_metric("amount", amount, cmp_amount, AMOUNT_BINS)
    for field in ANOMALY_FIELDS:
        continuous[field] = _continuous_metric(field, ref[field], cmp[field], PROBABILITY_BINS)

    prediction = {
        "fraud_probability": _continuous_metric("fraud_probability", ref.fraud_probability, cmp.fraud_probability, PROBABILITY_BINS),
        "reference_alert_count": int(ref.alert.sum()),
        "comparison_alert_count": int(cmp.alert.sum()),
        "reference_alert_rate": float(ref.alert.mean()) if len(ref) else 0.0,
        "comparison_alert_rate": float(cmp.alert.mean()) if len(cmp) else 0.0,
        "alert_rate_change": float(cmp.alert.mean() - ref.alert.mean()) if len(ref) and len(cmp) else None,
        "reference_above_threshold_count": int(pd.to_numeric(ref.fraud_probability).ge(threshold).sum()),
        "comparison_above_threshold_count": int(pd.to_numeric(cmp.fraud_probability).ge(threshold).sum()),
        "frozen_threshold": threshold,
        "fraud_probability_quantiles": {
            "reference": {key: float(value) for key, value in pd.to_numeric(ref.fraud_probability).quantile([.05,.25,.5,.75,.95]).items()},
            "comparison": {key: float(value) for key, value in pd.to_numeric(cmp.fraud_probability).quantile([.05,.25,.5,.75,.95]).items()},
        },
    }
    categorical = {}
    if ref_md is not None and "type" in ref_md.columns:
        categorical["type"] = _categorical_metric("type", ref_md.type, cmp_md.type)

    findings = []
    for metric in list(continuous.values()) + list(categorical.values()):
        findings.append({"feature": metric["feature"], "reference_window": reference_window.window_id, "comparison_window": comparison_window.window_id, "sample_counts": {"reference": metric["reference_count"], "comparison": metric["comparison_count"]}, "metrics": {key: metric[key] for key in ("ks_statistic", "psi", "jensen_shannon_divergence", "missingness_rate_change") if key in metric}, "interpretation": metric["interpretation"], "limitations": "No significance or degradation claim is made; metric sensitivity depends on bins, sample sizes, and missingness."})
    findings.append({"feature": "alert_rate", "reference_window": reference_window.window_id, "comparison_window": comparison_window.window_id, "sample_counts": {"reference": len(ref), "comparison": len(cmp)}, "metrics": {"value": prediction["alert_rate_change"]}, "interpretation": "Descriptive change in frozen alert rate.", "limitations": "Alert-rate change does not establish model degradation or fraud prevalence change."})

    return {
        "schema_version": DRIFT_SCHEMA_VERSION,
        "execution_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "retrospective_simulated_data": True,
        "reference_window": reference_window.to_dict(),
        "comparison_window": comparison_window.to_dict(),
        "reference_transaction_count": len(ref),
        "comparison_transaction_count": len(cmp),
        "source_artifacts": source_artifacts or {"frozen_threshold": threshold},
        "data_drift": {"continuous": continuous, "categorical": categorical},
        "prediction_drift": prediction,
        "findings": findings,
        "limitations": ["PSI and fixed bins are descriptive and bin-sensitive.", "KS and Jensen-Shannon values are not significance tests here.", "Small samples, constant values, and missingness can make metrics unstable.", "Drift does not imply model degradation or fraud.", "Ground-truth labels, account identifiers, and reviewer content are excluded."],
    }
