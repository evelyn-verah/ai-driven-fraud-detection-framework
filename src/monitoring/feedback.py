"""Read-only analysis of Module 6 append-only review events."""
from __future__ import annotations

from datetime import datetime, timezone
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

from src.dashboard.config import FEEDBACK_DB_PATH, FROZEN_THRESHOLD
from src.dashboard.feedback_store import REVIEW_STATUSES
FEEDBACK_SCHEMA_VERSION = "module7_stage4_feedback_v1"
REQUIRED_COLUMNS = {"event_id", "row_id", "status", "reviewer_label", "notes", "created_at_utc"}
PROBABILITY_BINS = np.linspace(0.0, 1.0, 11)


class FeedbackDataError(ValueError):
    """Raised when a feedback database cannot satisfy its data contract."""


def _read_only_connection(path: Path):
    uri = "file:" + path.resolve().as_posix() + "?mode=ro"
    return sqlite3.connect(uri, uri=True)


def _parse_utc(value):
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise FeedbackDataError("invalid created_at_utc value") from exc
    if parsed.tzinfo is None:
        raise FeedbackDataError("created_at_utc must include a timezone")
    return parsed.astimezone(timezone.utc)


def load_feedback_events(path=FEEDBACK_DB_PATH):
    """Return validated internal events without opening the demonstration DB."""
    path = Path(path)
    if not path.is_file():
        return pd.DataFrame(columns=sorted(REQUIRED_COLUMNS)), {"status": "missing", "path": str(path)}
    try:
        with _read_only_connection(path) as connection:
            table = connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='review_events'").fetchone()
            if table is None:
                raise FeedbackDataError("review_events table is missing")
            columns = {row[1] for row in connection.execute("PRAGMA table_info(review_events)").fetchall()}
            if not REQUIRED_COLUMNS.issubset(columns):
                raise FeedbackDataError("review_events schema is missing required columns")
            rows = connection.execute("SELECT event_id,row_id,status,reviewer_label,notes,created_at_utc FROM review_events ORDER BY created_at_utc,event_id").fetchall()
    except sqlite3.Error as exc:
        raise FeedbackDataError("unable to read feedback database") from exc
    events = pd.DataFrame(rows, columns=["event_id", "row_id", "status", "reviewer_label", "notes", "created_at_utc"])
    if events.empty:
        return events, {"status": "empty", "path": str(path)}
    if events.event_id.isna().any() or events.event_id.duplicated().any():
        raise FeedbackDataError("event_id values must be present and unique")
    numeric_row_ids = pd.to_numeric(events.row_id, errors="coerce")
    if events.row_id.isna().any() or numeric_row_ids.isna().any() or (numeric_row_ids < 0).any() or (numeric_row_ids % 1 != 0).any():
        raise FeedbackDataError("row_id values must be non-negative integers")
    if not events.status.isin(REVIEW_STATUSES).all():
        raise FeedbackDataError("unsupported review status")
    events["row_id"] = numeric_row_ids.astype("int64")
    events["created_at"] = events.created_at_utc.map(_parse_utc)
    events["utc_date"] = events.created_at.map(lambda value: value.date().isoformat())
    stat = path.stat()
    return events, {"status": "ok", "path": str(path), "file_size_bytes": stat.st_size, "mtime_utc": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(), "read_consistency": "single read-only SQLite connection"}


def _distribution(counts, total):
    return [{"status": status, "count": int(counts.get(status, 0)), "proportion": float(counts.get(status, 0) / total) if total else 0.0} for status in REVIEW_STATUSES]


def _score_alignment(events, scores, threshold=FROZEN_THRESHOLD):
    if scores is None:
        return {"available": False, "reason": "score cache was not supplied"}
    required = {"row_id", "fraud_probability", "alert"}
    if not required.issubset(scores.columns):
        raise FeedbackDataError("score cache is missing alignment columns")
    if scores.row_id.duplicated().any():
        raise FeedbackDataError("score cache contains duplicate row_id values")
    lookup = scores.set_index("row_id")[["fraud_probability", "alert"]]
    aligned = events[events.row_id.isin(lookup.index)].copy()
    aligned["fraud_probability"] = aligned.row_id.map(lookup.fraud_probability)
    aligned["alert"] = aligned.row_id.map(lookup.alert)
    aligned["risk_band"] = pd.cut(aligned.fraud_probability, PROBABILITY_BINS, include_lowest=True, right=True)
    aligned_count = len(aligned)
    missing_count = len(events) - aligned_count
    status_by_band = {}
    for band, group in aligned.groupby("risk_band", observed=False):
        label = str(band)
        status_by_band[label] = _distribution(group.status.value_counts().to_dict(), len(group))
    return {
        "available": True,
        "event_count_aligned": aligned_count,
        "event_count_missing_score": missing_count,
        "alerted_event_count": int(aligned.alert.sum()),
        "non_alerted_event_count": int((~aligned.alert.astype(bool)).sum()),
        "risk_band_edges": [float(edge) for edge in PROBABILITY_BINS],
        "status_distribution_by_risk_band": status_by_band,
        "escalation_count_by_risk_band": {str(band): int((group.status == "Escalated").sum()) for band, group in aligned.groupby("risk_band", observed=False)},
        "frozen_threshold": threshold,
    }


def analyze_feedback(path=FEEDBACK_DB_PATH, scores=None, start_utc=None, end_utc=None, threshold=FROZEN_THRESHOLD):
    """Produce a label-free, deterministic summary from a read-only snapshot."""
    events, source = load_feedback_events(path)
    output = {
        "schema_version": FEEDBACK_SCHEMA_VERSION,
        "analysis_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "source_database": source,
        "time_window": {"start_utc": start_utc, "end_utc": end_utc},
        "limitations": ["Analyst statuses are workflow assessments, not verified fraud labels.", "Historical event counts and latest status are distinct; latest status is not a final outcome.", "Feedback analysis does not modify model scores, thresholds, or training data."],
    }
    if source["status"] in {"missing", "empty"}:
        output.update({"event_count": 0, "distinct_reviewed_transaction_count": 0, "status_distribution": _distribution({}, 0), "data_quality": {"status": source["status"]}, "risk_score_alignment": {"available": False, "reason": "no review events"}})
        return output
    if start_utc is not None:
        start = _parse_utc(start_utc)
        events = events[events.created_at >= start]
    if end_utc is not None:
        end = _parse_utc(end_utc)
        events = events[events.created_at <= end]
    total = len(events)
    per_transaction = events.groupby("row_id").size() if total else pd.Series(dtype="int64")
    status_counts = events.status.value_counts().to_dict()
    latest = events.sort_values(["created_at", "event_id"]).drop_duplicates("row_id", keep="last") if total else events
    output.update({
        "event_count": total,
        "distinct_reviewed_transaction_count": int(events.row_id.nunique()),
        "status_distribution": _distribution(status_counts, total),
        "escalation_count": int((events.status == "Escalated").sum()),
        "reviews_per_transaction": {"min": int(per_transaction.min()) if total else 0, "max": int(per_transaction.max()) if total else 0, "mean": float(per_transaction.mean()) if total else 0.0, "repeat_review_transaction_count": int((per_transaction > 1).sum()) if total else 0},
        "repeat_review_event_count": int(total - len(per_transaction)) if total else 0,
        "activity_by_utc_date": [{"utc_date": str(date), "event_count": int(count)} for date, count in events.groupby("utc_date", sort=True).size().items()] if total else [],
        "latest_status_distribution": _distribution(latest.status.value_counts().to_dict(), len(latest)),
        "data_quality": {"status": "ok", "invalid_rows": 0},
        "risk_score_alignment": _score_alignment(events, scores, threshold),
    })
    return output
