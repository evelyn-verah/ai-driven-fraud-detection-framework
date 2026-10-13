"""Deterministic, read-only monitoring calculations over frozen outputs."""
from __future__ import annotations
import hashlib, json, os, tempfile
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import pandas as pd

from src.dashboard.config import SCORE_CACHE_PATH, METADATA_INDEX_PATH, PAYSIM_RAW_PATH, FROZEN_THRESHOLD, HOLDOUT_START_STEP, HOLDOUT_END_STEP
from src.dashboard.data_access import load_score_cache
from src.dashboard.metadata_index import load_metadata_index
from .contracts import MONITORING_SCHEMA_VERSION, MonitoringWindow, validate_windows

ROOT = Path(__file__).resolve().parents[2]
MODULE4_MANIFEST = ROOT / "artifacts" / "module4_final_holdout_recovery_v1" / "recovery_manifest.json"
REQUIRED = ["row_id", "step", "fraud_probability", "baseline_anomaly_intensity", "behavioral_anomaly_intensity", "rule_score_context", "alert"]
ANOMALY_FIELDS = ["baseline_anomaly_intensity", "behavioral_anomaly_intensity"]

def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()

def _validate_frame(frame, threshold=FROZEN_THRESHOLD, start=HOLDOUT_START_STEP, end=HOLDOUT_END_STEP):
    missing = [c for c in REQUIRED if c not in frame.columns]
    if missing: raise ValueError(f"missing monitoring columns: {missing}")
    if frame["row_id"].duplicated().any(): raise ValueError("duplicate row_id")
    if frame["row_id"].isna().any() or not pd.api.types.is_integer_dtype(frame["row_id"]): raise ValueError("row_id must be integer")
    if ((frame.step < start) | (frame.step > end) | frame.step.isna()).any(): raise ValueError("invalid PaySim step")
    for col in REQUIRED[2:6]:
        values = pd.to_numeric(frame[col], errors="coerce")
        if values.notna().any() and (~np.isfinite(values.dropna())).any(): raise ValueError(f"non-finite {col}")
        if values.notna().any() and ((values.dropna() < 0) | (values.dropna() > 1)).any(): raise ValueError(f"out-of-range {col}")
    if not pd.api.types.is_bool_dtype(frame.alert): raise ValueError("alert must be boolean")
    p = pd.to_numeric(frame.fraud_probability, errors="coerce")
    expected = p.ge(threshold)
    if not frame.loc[p.notna(), "alert"].eq(expected[p.notna()]).all(): raise ValueError("alert does not match frozen threshold")

def load_frozen_inputs(include_metadata=True):
    cache = load_score_cache(SCORE_CACHE_PATH)
    metadata = None
    if include_metadata:
        metadata = load_metadata_index(METADATA_INDEX_PATH, PAYSIM_RAW_PATH, cache).frame.copy()
    source = {
        "score_cache_path": str(SCORE_CACHE_PATH),
        "score_cache_sha256": sha256_file(SCORE_CACHE_PATH),
        "module4_manifest_path": str(MODULE4_MANIFEST),
        "module4_manifest_sha256": sha256_file(MODULE4_MANIFEST) if MODULE4_MANIFEST.exists() else None,
        "architecture_version": "module4_stage4_rf_primary_v1",
        "frozen_threshold": FROZEN_THRESHOLD,
        "step_range": [HOLDOUT_START_STEP, HOLDOUT_END_STEP],
    }
    sidecar_manifest = Path(METADATA_INDEX_PATH) / "manifest.json"
    source["metadata_sidecar_path"] = str(METADATA_INDEX_PATH)
    source["metadata_sidecar_manifest_sha256"] = sha256_file(sidecar_manifest) if sidecar_manifest.exists() else None
    if sidecar_manifest.exists():
        with sidecar_manifest.open("r", encoding="utf-8") as fh:
            source["metadata_sidecar_parquet_sha256"] = json.load(fh).get("parquet_sha256")
    source["complete_step_counts"] = {str(int(step)): int(count) for step, count in cache.frame.groupby("step", sort=True).size().items()}
    return cache.frame.copy(), metadata, source

def _stats(values):
    s = pd.to_numeric(values, errors="coerce")
    valid = s.dropna().astype(float)
    out = {"count": int(len(valid)), "missing_count": int(s.isna().sum()), "missing_rate": float(s.isna().mean()) if len(s) else 0.0}
    if len(valid):
        q = valid.quantile([.05,.25,.5,.75,.95])
        out.update({"min": float(valid.min()), "max": float(valid.max()), "mean": float(valid.mean()), "median": float(valid.median()), "quantiles": {"p05": float(q.loc[.05]), "p25": float(q.loc[.25]), "p50": float(q.loc[.5]), "p75": float(q.loc[.75]), "p95": float(q.loc[.95])}})
    else: out.update({"min": None, "max": None, "mean": None, "median": None, "quantiles": {}})
    return out

def _bins(values):
    labels = [f"{i/10:.1f}-{(i+1)/10:.1f}" for i in range(10)]
    cats = pd.cut(pd.to_numeric(values, errors="coerce"), np.linspace(0,1,11), labels=labels, include_lowest=True)
    counts = cats.value_counts(sort=False)
    total = int(cats.notna().sum())
    return [{"bin": label, "count": int(counts.get(label, 0)), "proportion": float(counts.get(label, 0)/total) if total else 0.0} for label in labels]

def _one_summary(frame, metadata=None):
    n = len(frame)
    alert_count = int(frame.alert.sum())
    per_step = []
    for step, group in frame.groupby("step", sort=True):
        count = len(group); alerts = int(group.alert.sum())
        per_step.append({"step": int(step), "transaction_count": count, "alert_count": alerts, "alert_rate": float(alerts/count) if count else 0.0})
    score = _stats(frame.fraud_probability); score["bins"] = _bins(frame.fraud_probability)
    p = pd.to_numeric(frame.fraud_probability, errors="coerce")
    score["above_frozen_threshold_count"] = int((p >= FROZEN_THRESHOLD).sum())
    score["above_frozen_threshold_proportion"] = float((p >= FROZEN_THRESHOLD).mean()) if n else 0.0
    anomaly = {name: {**_stats(frame[name]), "bins": _bins(frame[name]), "interpretation": "contextual anomaly intensity, not a fraud probability"} for name in ANOMALY_FIELDS}
    result = {"transaction_count": n, "alert_count": alert_count, "alert_rate": float(alert_count/n) if n else 0.0, "by_step": per_step, "fraud_probability": score, "anomaly": anomaly, "missingness": {c: _stats(frame[c])["missing_count"] for c in ["fraud_probability", *ANOMALY_FIELDS]}}
    if metadata is not None:
        md = metadata[metadata.row_id.isin(frame.row_id)].copy()
        score_steps = frame.set_index("row_id")["step"].sort_index()
        metadata_steps = md.set_index("row_id")["step"].sort_index()
        if len(md) != n or not np.array_equal(metadata_steps.to_numpy(), score_steps.to_numpy()): raise ValueError("metadata row_id/step alignment failure")
        if "type" in md:
            counts = md["type"].value_counts(dropna=False).sort_index()
            result["transaction_types"] = [{"type": None if pd.isna(k) else str(k), "count": int(v), "proportion": float(v/n) if n else 0.0} for k,v in counts.items()]
        if "amount" in md: result["amount"] = _stats(md["amount"])
    return result

def _validate_complete_windows(frame, windows, expected_step_counts):
    if expected_step_counts is None:
        raise ValueError("expected_step_counts are required to publish complete-step monitoring windows")
    normalized = {int(step): int(count) for step, count in expected_step_counts.items()}
    for window in windows:
        expected_steps = list(range(window.start_step, window.end_step + 1))
        missing = [step for step in expected_steps if step not in normalized]
        if missing:
            raise ValueError(f"window contains steps without authoritative counts: {missing}")
        observed = frame.loc[frame.step.between(window.start_step, window.end_step)].groupby("step").size().to_dict()
        mismatches = {step: (int(observed.get(step, 0)), normalized[step]) for step in expected_steps if int(observed.get(step, 0)) != normalized[step]}
        if mismatches:
            raise ValueError(f"window is not complete against authoritative counts: {mismatches}")

def summarize_monitoring(frame, metadata=None, windows=None, source_artifacts=None, threshold=FROZEN_THRESHOLD, expected_step_counts=None):
    _validate_frame(frame, threshold)
    if windows is None: windows = [MonitoringWindow("full_holdout", HOLDOUT_START_STEP, HOLDOUT_END_STEP, "retrospective summary", "frozen complete-step source range")]
    windows = validate_windows(windows)
    if expected_step_counts is None and source_artifacts:
        expected_step_counts = source_artifacts.get("complete_step_counts")
    _validate_complete_windows(frame, windows, expected_step_counts)
    result = {"schema_version": MONITORING_SCHEMA_VERSION, "execution_timestamp_utc": datetime.now(timezone.utc).isoformat(), "retrospective_simulated_data": True, "source_artifacts": source_artifacts or {"frozen_threshold": threshold}, "windows": [w.to_dict() for w in windows], "summary": _one_summary(frame, metadata), "window_summaries": [], "limitations": ["Descriptive summaries over simulated PaySim transactions; no real-world performance inference.", "Anomaly intensities are contextual indicators and do not alter Random Forest alert decisions.", "Ground-truth labels, account identifiers, and reviewer-entered content are excluded from monitoring outputs."]}
    for w in windows:
        selected = frame[(frame.step >= w.start_step) & (frame.step <= w.end_step)]
        md = metadata[metadata.row_id.isin(selected.row_id)] if metadata is not None else None
        expected_count = sum(int(expected_step_counts[str(step)] if str(step) in expected_step_counts else expected_step_counts[step]) for step in range(w.start_step, w.end_step + 1))
        result["window_summaries"].append({"window_id": w.window_id, "start_step": w.start_step, "end_step": w.end_step, "complete_step_window": True, "expected_transaction_count": expected_count, "summary": _one_summary(selected, md)})
    return result

def write_monitoring_result(result, destination):
    destination = Path(destination); destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix=destination.name + ".", suffix=".tmp", dir=destination.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh: json.dump(result, fh, indent=2, sort_keys=True, allow_nan=False); fh.write("\n")
        os.replace(temp, destination)
    except Exception:
        try: os.unlink(temp)
        except OSError: pass
        raise
    return destination
