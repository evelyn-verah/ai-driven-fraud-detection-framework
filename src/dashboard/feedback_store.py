"""Local append-only analyst review storage, isolated from frozen artifacts."""
from __future__ import annotations

import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

REVIEW_STATUSES = (
    "Unreviewed",
    "Needs Investigation",
    "False Positive Suspected",
    "Escalated",
    "Reviewed / Closed",
)
MAX_REVIEWER_LENGTH = 128
MAX_NOTES_LENGTH = 4000


@dataclass(frozen=True)
class ReviewEvent:
    event_id: str
    row_id: int
    status: str
    reviewer_label: str
    notes: str | None
    created_at_utc: str


def _validate(row_id: int, status: str, reviewer_label: str, notes: str | None) -> tuple[int, str, str, str | None]:
    if isinstance(row_id, bool) or not isinstance(row_id, int) or row_id < 0:
        raise ValueError("row_id must be a non-negative integer")
    if status not in REVIEW_STATUSES:
        raise ValueError("invalid review status")
    if not isinstance(reviewer_label, str) or not reviewer_label.strip() or len(reviewer_label) > MAX_REVIEWER_LENGTH:
        raise ValueError("reviewer label must be non-empty and at most 128 characters")
    if notes is not None and (not isinstance(notes, str) or len(notes) > MAX_NOTES_LENGTH):
        raise ValueError("notes must be text of at most 4000 characters")
    return row_id, status, reviewer_label.strip(), notes


def initialize_database(path: str | Path) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(target) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute(
            """CREATE TABLE IF NOT EXISTS review_events (
                event_id TEXT PRIMARY KEY,
                row_id INTEGER NOT NULL CHECK (row_id >= 0),
                status TEXT NOT NULL CHECK (status IN ('Unreviewed','Needs Investigation','False Positive Suspected','Escalated','Reviewed / Closed')),
                reviewer_label TEXT NOT NULL CHECK (length(reviewer_label) BETWEEN 1 AND 128),
                notes TEXT CHECK (notes IS NULL OR length(notes) <= 4000),
                created_at_utc TEXT NOT NULL
            )"""
        )
        connection.execute("CREATE INDEX IF NOT EXISTS idx_review_events_row_id_time ON review_events(row_id, created_at_utc)")
    return target


def save_review(path: str | Path, row_id: int, status: str, reviewer_label: str, notes: str | None = None) -> ReviewEvent:
    row_id, status, reviewer_label, notes = _validate(row_id, status, reviewer_label, notes)
    event = ReviewEvent(str(uuid.uuid4()), row_id, status, reviewer_label, notes, datetime.now(timezone.utc).isoformat())
    try:
        initialize_database(path)
        with sqlite3.connect(path) as connection:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute(
                "INSERT INTO review_events(event_id,row_id,status,reviewer_label,notes,created_at_utc) VALUES (?,?,?,?,?,?)",
                (event.event_id, event.row_id, event.status, event.reviewer_label, event.notes, event.created_at_utc),
            )
            connection.commit()
    except sqlite3.Error as exc:
        raise OSError(f"unable to save review event: {exc}") from exc
    return event


def _read_rows(path: str | Path, row_id: int) -> list[ReviewEvent]:
    if isinstance(row_id, bool) or not isinstance(row_id, int) or row_id < 0:
        raise ValueError("row_id must be a non-negative integer")
    if not Path(path).is_file():
        return []
    try:
        with sqlite3.connect(path) as connection:
            rows = connection.execute(
                "SELECT event_id,row_id,status,reviewer_label,notes,created_at_utc FROM review_events WHERE row_id = ? ORDER BY created_at_utc, event_id",
                (row_id,),
            ).fetchall()
    except sqlite3.Error as exc:
        raise OSError(f"unable to read review history: {exc}") from exc
    return [ReviewEvent(*row) for row in rows]


def review_history(path: str | Path, row_id: int) -> list[ReviewEvent]:
    return _read_rows(path, row_id)


def latest_review(path: str | Path, row_id: int) -> ReviewEvent | None:
    events = _read_rows(path, row_id)
    return events[-1] if events else None
