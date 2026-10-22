from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.dashboard.secure_app import (
    alert_status_label,
    analyst_score_table,
    format_probability,
    risk_decision_explanation,
)


def _scores() -> pd.DataFrame:
    return pd.DataFrame({
        "row_id": [10, 11],
        "step": [378, 378],
        "fraud_probability": [0.825, 0.12],
        "baseline_anomaly_intensity": [0.62, 0.18],
        "behavioral_anomaly_intensity": [0.71, 0.21],
        "rule_score_context": [0.5, 0.0],
        "alert": [True, False],
    })


def test_probability_and_alert_presentation_support_alerted_transaction() -> None:
    assert format_probability(0.825) == "82.50%"
    assert alert_status_label(True) == "Flagged for Investigation"
    explanation = risk_decision_explanation(0.825, 0.3494391872980995, True)
    assert "82.50%" in explanation
    assert "34.94%" in explanation
    assert "flagged for investigation" in explanation
    assert "does not establish" in explanation


def test_probability_and_alert_presentation_support_non_alerted_transaction() -> None:
    assert alert_status_label(False) == "Not Flagged"
    explanation = risk_decision_explanation(0.12, 0.3494391872980995, False)
    assert "12.00%" in explanation
    assert "does not exceed" in explanation
    assert "not flagged" in explanation


def test_analyst_table_renames_and_formats_without_mutating_scores() -> None:
    source = _scores()
    original = source.copy(deep=True)
    display = analyst_score_table(source)
    assert list(display.columns) == [
        "Transaction ID", "Simulation Step", "Fraud Risk (%)",
        "Baseline Anomaly Indicator", "Behavioral Anomaly Indicator",
        "Rule-Based Context", "Fraud Alert",
    ]
    assert display.loc[0, "Fraud Risk (%)"] == "82.50%"
    assert display.loc[0, "Fraud Alert"] == "Flagged for Investigation"
    assert display.loc[1, "Fraud Risk (%)"] == "12.00%"
    assert display.loc[1, "Fraud Alert"] == "Not Flagged"
    pd.testing.assert_frame_equal(source, original)


def test_secure_dashboard_has_no_raw_json_rendering() -> None:
    source = (Path(__file__).resolve().parents[1] / "src/dashboard/secure_app.py").read_text(encoding="utf-8")
    assert "st.json" not in source
    assert "Advanced Technical Details (JSON)" not in source
