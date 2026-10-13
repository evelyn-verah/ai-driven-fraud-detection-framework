import sqlite3

import pytest

from src.dashboard.feedback_store import REVIEW_STATUSES, latest_review, review_history, save_review


def test_initial_state_and_append_only_history(tmp_path):
    db = tmp_path / "feedback.sqlite3"
    assert latest_review(db, 7) is None
    first = save_review(db, 7, "Needs Investigation", "analyst-a", "Check recipient history")
    second = save_review(db, 7, "Reviewed / Closed", "analyst-b")
    assert latest_review(db, 7) == second
    history = review_history(db, 7)
    assert [event.event_id for event in history] == [first.event_id, second.event_id]
    assert history[0].notes == "Check recipient history"


def test_reopen_persists_and_no_ground_truth_columns(tmp_path):
    db = tmp_path / "feedback.sqlite3"
    save_review(db, 3, "Escalated", "reviewer", "possible mule pattern")
    with sqlite3.connect(db) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(review_events)")}
    assert "isFraud" not in columns
    assert latest_review(db, 3).status == "Escalated"


@pytest.mark.parametrize("status", ["", "fraud", None])
def test_invalid_status_rejected(tmp_path, status):
    with pytest.raises(ValueError):
        save_review(tmp_path / "db.sqlite3", 1, status, "reviewer")


def test_bounded_inputs_and_invalid_row(tmp_path):
    db = tmp_path / "db.sqlite3"
    with pytest.raises(ValueError):
        save_review(db, -1, REVIEW_STATUSES[0], "reviewer")
    with pytest.raises(ValueError):
        save_review(db, 1, REVIEW_STATUSES[0], "")
    with pytest.raises(ValueError):
        save_review(db, 1, REVIEW_STATUSES[0], "r", "x" * 4001)


def test_database_write_failure_is_safe(tmp_path):
    db_directory = tmp_path / "as_directory"
    db_directory.mkdir()
    with pytest.raises(OSError):
        save_review(db_directory, 1, REVIEW_STATUSES[0], "reviewer")
