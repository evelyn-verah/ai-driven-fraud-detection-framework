from __future__ import annotations

from pathlib import Path

import pytest

from src.dashboard import demo_app
from src.dashboard.config import DEMONSTRATION_FEEDBACK_DB_PATH, FEEDBACK_DB_PATH
from src.dashboard.secure_app import SecureDashboard
from src.security.dashboard_access import AuthorizationError, issue_local_context


def test_demo_launcher_is_separate_from_production_launcher() -> None:
    root = Path(__file__).resolve().parents[1]
    production = (root / "src/dashboard/app.py").read_text(encoding="utf-8")
    demo = (root / "src/dashboard/demo_app.py").read_text(encoding="utf-8")
    assert "issue_local_context" not in production
    assert "issue_local_context" in demo
    assert "127.0.0.1" in demo


@pytest.mark.parametrize("address", ["", "localhost", "0.0.0.0", "::", "192.168.1.10"])
def test_demo_rejects_non_explicit_loopback_configuration(address: str) -> None:
    assert not demo_app.is_loopback_configuration(address)


def test_demo_accepts_only_ipv4_loopback() -> None:
    assert demo_app.is_loopback_configuration("127.0.0.1")


def test_demo_context_preserves_authorization() -> None:
    context = issue_local_context("Analyst", trusted_local_identity=True)
    dashboard = SecureDashboard(
        context,
        feedback_db=DEMONSTRATION_FEEDBACK_DB_PATH,
        demonstration_db=DEMONSTRATION_FEEDBACK_DB_PATH,
        production_only=False,
    )
    assert dashboard.feedback_db == DEMONSTRATION_FEEDBACK_DB_PATH
    assert dashboard.feedback_db != FEEDBACK_DB_PATH
    with pytest.raises(AuthorizationError):
        SecureDashboard(None).load_scores()


def test_demo_feedback_round_trip_uses_demo_database(tmp_path: Path) -> None:
    database = tmp_path / "reviews.sqlite3"
    context = issue_local_context("Analyst", trusted_local_identity=True)
    dashboard = SecureDashboard(
        context,
        trusted_root=tmp_path,
        feedback_db=database,
        demonstration_db=database,
        production_only=False,
    )
    event = dashboard.submit_review(0, "Escalated", "demo-analyst", "presentation note")
    assert event.row_id == 0
    assert dashboard.feedback_summary() == {"event_count": 1, "status_counts": {"Escalated": 1}}
    assert not (tmp_path / "production_reviews.sqlite3").exists()


def test_secure_launcher_defaults_remain_production_safe() -> None:
    source = (Path(__file__).resolve().parents[1] / "src/dashboard/app.py").read_text(encoding="utf-8")
    assert "streamlit_main()" in source
    assert "demo_app" not in source
