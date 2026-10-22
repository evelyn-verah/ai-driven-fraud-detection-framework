from __future__ import annotations

from pathlib import Path

import pytest
import pandas as pd

from src.dashboard.data_access import filter_scores, paginate_scores
from src.dashboard.secure_app import SecureDashboard
from src.security.dashboard_access import AuthorizationError


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src/dashboard/secure_app.py"


def test_dashboard_has_five_stateful_analyst_sections() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    for section in (
        "Overview",
        "Transaction Explorer",
        "Transaction Details",
        "Fraud Intelligence",
        "Analyst Review",
    ):
        assert f'"{section}"' in source
    assert 'key="dashboard_section"' in source
    assert 'key="widget_selected_transaction"' in source
    assert 'key="widget_explorer_page"' in source
    assert '"selected_transaction_id"' in source


def test_explorer_provides_direct_investigation_navigation() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    assert "Investigate Selected Transaction" in source
    assert 'args=("Transaction Details",)' in source


def test_explorer_table_is_bounded_and_selection_is_visible() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    assert "height=420" in source
    assert 'display.insert(0, "Selected"' in source


def test_detail_loading_remains_authorized_before_retrieval() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    authorization = source.index('require_permission(context, "transaction.detail")')
    retrieval = source.index("build_retrieval_index", authorization)
    assert authorization < retrieval
    with pytest.raises(AuthorizationError):
        SecureDashboard(None).load_scores()


def test_alert_filter_values_use_frozen_alert_field_and_change_rows() -> None:
    scores = pd.DataFrame({
        "row_id": [10, 11, 12], "step": [378, 378, 379],
        "isFraud": [0, 1, 0], "fraud_probability": [0.1, 0.9, 0.2],
        "baseline_anomaly_intensity": [0.1, 0.2, 0.3],
        "behavioral_anomaly_intensity": [0.1, 0.2, 0.3],
        "rule_score_context": [0.0, 1.0, 0.0], "alert": [False, True, False],
    })
    all_rows = filter_scores(scores, step_min=378, step_max=379, alert=None)
    alerted = filter_scores(scores, step_min=378, step_max=379, alert=True)
    not_alerted = filter_scores(scores, step_min=378, step_max=379, alert=False)
    assert all_rows.row_id.tolist() == [10, 11, 12]
    assert alerted.row_id.tolist() == [11]
    assert alerted.alert.tolist() == [True]
    assert not_alerted.row_id.tolist() == [10, 12]
    assert not_alerted.alert.tolist() == [False, False]
    assert paginate_scores(not_alerted, page=1, page_size=25).row_id.tolist() != alerted.row_id.tolist()


def test_protected_detail_and_feedback_operations_are_not_rendered_without_selection() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    assert "No transaction is selected" in source
    assert "Load the selected transaction in Transaction Details" in source
    assert "dashboard.submit_review" in source
    assert "dashboard.feedback_summary" in source


def test_no_raw_json_is_visible_in_navigation_source() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    assert "st.json" not in source
    assert "Advanced Technical Details (JSON)" not in source


def test_explorer_filters_use_current_widget_values_and_reset_page() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    assert "alert_filter = controls[2].selectbox" in source
    assert "alert_value = None if alert_filter == \"All\" else alert_filter == \"Alerted\"" in source
    assert "filtered = filter_scores(cache.frame, step_min=step_min, step_max=step_max, alert=alert_value)" in source
    assert 'st.session_state["explorer_page"] = 1' in source
