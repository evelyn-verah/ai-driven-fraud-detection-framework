import hashlib
import json
import sqlite3
from pathlib import Path

import pandas as pd
import pytest

from src.dashboard.config import FEEDBACK_DB_PATH, DEMONSTRATION_FEEDBACK_DB_PATH
from src.dashboard.feedback_store import initialize_database
from src.monitoring.feedback import FeedbackDataError, analyze_feedback, load_feedback_events


def make_db(tmp_path, rows=()):
    path = tmp_path / "reviews.sqlite3"
    initialize_database(path)
    with sqlite3.connect(path) as connection:
        for row in rows:
            connection.execute("INSERT INTO review_events(event_id,row_id,status,reviewer_label,notes,created_at_utc) VALUES (?,?,?,?,?,?)", row)
        connection.commit()
    return path


def scores():
    return pd.DataFrame({"row_id": [10, 11], "fraud_probability": [0.1, 0.8], "alert": [False, True]})


ROWS = [
    ("e1", 10, "Needs Investigation", "Reviewer A", "private note", "2026-01-01T10:00:00+00:00"),
    ("e2", 10, "Escalated", "Reviewer B", None, "2026-01-02T10:00:00Z"),
    ("e3", 11, "False Positive Suspected", "Reviewer C", "do not export", "2026-01-02T11:00:00+00:00"),
]


def test_empty_and_missing_database(tmp_path):
    empty = make_db(tmp_path)
    result = analyze_feedback(empty)
    assert result["event_count"] == 0 and result["source_database"]["status"] == "empty"
    missing = analyze_feedback(tmp_path / "missing.sqlite3")
    assert missing["event_count"] == 0 and missing["source_database"]["status"] == "missing"


def test_status_counts_distinct_repeats_latest_and_dates(tmp_path):
    result = analyze_feedback(make_db(tmp_path, ROWS), scores=scores())
    assert result["event_count"] == 3
    assert result["distinct_reviewed_transaction_count"] == 2
    assert result["escalation_count"] == 1
    assert result["reviews_per_transaction"]["repeat_review_transaction_count"] == 1
    assert result["repeat_review_event_count"] == 1
    assert [item["event_count"] for item in result["activity_by_utc_date"]] == [1, 2]
    latest = {item["status"]: item["count"] for item in result["latest_status_distribution"]}
    assert latest["Escalated"] == 1 and latest["False Positive Suspected"] == 1


def test_utc_date_window_filter(tmp_path):
    result = analyze_feedback(make_db(tmp_path, ROWS), start_utc="2026-01-02T00:00:00Z", end_utc="2026-01-02T23:59:59Z")
    assert result["event_count"] == 2 and result["distinct_reviewed_transaction_count"] == 2


def test_score_alignment_bands_alerts_and_missing_ids(tmp_path):
    result = analyze_feedback(make_db(tmp_path, ROWS), scores=scores())
    alignment = result["risk_score_alignment"]
    assert alignment["event_count_aligned"] == 3
    assert alignment["event_count_missing_score"] == 0
    assert alignment["alerted_event_count"] == 1
    assert alignment["non_alerted_event_count"] == 2
    assert alignment["frozen_threshold"] == 0.3494391872980995
    missing = analyze_feedback(make_db(tmp_path, [("e4", 999, "Escalated", "R", None, ROWS[0][-1])]), scores=scores())
    assert missing["risk_score_alignment"]["event_count_missing_score"] == 1


def test_malformed_schema_and_invalid_timestamp(tmp_path):
    bad = tmp_path / "bad.sqlite3"
    with sqlite3.connect(bad) as connection:
        connection.execute("CREATE TABLE review_events (event_id TEXT)")
    with pytest.raises(FeedbackDataError): load_feedback_events(bad)
    invalid = make_db(tmp_path, [("bad", 1, "Escalated", "R", None, "2026-01-01 10:00:00")])
    with pytest.raises(FeedbackDataError): analyze_feedback(invalid)


def test_no_reviewer_notes_labels_or_demo_access(tmp_path):
    path = make_db(tmp_path, ROWS)
    result = analyze_feedback(path, scores=scores())
    text = json.dumps(result, sort_keys=True)
    assert "Reviewer A" not in text and "private note" not in text
    assert "isFraud" not in text and "verified false positive" not in text.lower()
    assert Path(FEEDBACK_DB_PATH).name == "production_reviews.sqlite3"
    assert Path(DEMONSTRATION_FEEDBACK_DB_PATH).name == "reviews.sqlite3"


def test_database_is_unchanged_by_read_only_analysis(tmp_path):
    path = make_db(tmp_path, ROWS)
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    analyze_feedback(path, scores=scores())
    after = hashlib.sha256(path.read_bytes()).hexdigest()
    assert before == after


def test_deterministic_metrics_except_timestamp(tmp_path):
    path = make_db(tmp_path, ROWS)
    first = analyze_feedback(path, scores=scores()); second = analyze_feedback(path, scores=scores())
    first.pop("analysis_timestamp_utc"); second.pop("analysis_timestamp_utc")
    assert first == second
