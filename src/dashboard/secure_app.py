"""Module 6 V1.2 secure dashboard execution boundary.

This entry point is intentionally separate from the historical Streamlit
application. It accepts only an already-issued Stage 4 context; it never
turns a URL, widget, or role string into an authenticated identity.
"""
from __future__ import annotations

from pathlib import Path
from collections.abc import Mapping
from typing import Any

import pandas as pd

from src.dashboard.config import (
    AUTHORITATIVE_KB_PATH,
    AUTHORITATIVE_KB_VERSION,
    FEEDBACK_DB_PATH,
    METADATA_INDEX_PATH,
    PAYSIM_RAW_PATH,
    ROOT,
    SCORE_CACHE_PATH,
)
from src.risk_engine.final_architecture import FinalRiskAssessmentConfig
from src.dashboard.data_access import ScoreCache, load_score_cache
from src.dashboard.data_access import filter_scores, overview_aggregations, paginate_scores
from src.dashboard.metadata_index import load_metadata_index
from src.dashboard.feedback_store import REVIEW_STATUSES
from src.dashboard.details import build_transaction_details
from src.fraud_intelligence.retrieval import RetrievalIndex, build_retrieval_index
from src.security.dashboard_access import (
    AuthorizationError,
    DashboardContext,
    authorized_detail,
    authorized_scores,
    require_permission,
    safe_feedback_summary,
    submit_review,
)
from src.security.storage_security import secure_path


class SecureDashboard:
    """Authorized, analyst-safe operations for a controlled local launch."""

    def __init__(self, context: DashboardContext | None, *, trusted_root: str | Path = ROOT,
                 feedback_db: str | Path = FEEDBACK_DB_PATH,
                 demonstration_db: str | Path | None = None,
                 production_only: bool = True) -> None:
        self.context = context
        self.trusted_root = Path(trusted_root)
        self.feedback_db = Path(feedback_db)
        self.demonstration_db = Path(demonstration_db) if demonstration_db is not None else None
        self.production_only = production_only

    def load_scores(self, path: str | Path = SCORE_CACHE_PATH):
        require_permission(self.context, "dashboard.read")
        cache = load_score_cache(path)
        return authorized_scores(self.context, cache.frame)

    def load_transaction_detail(
        self, row_id: int, cache: ScoreCache, retrieval_index: RetrievalIndex,
        *, metadata_index: Any = None, raw_path: str | Path | None = None,
    ) -> dict[str, Any]:
        require_permission(self.context, "transaction.detail")
        details = build_transaction_details(
            row_id, cache, retrieval_index, metadata_index=metadata_index,
            raw_path=str(raw_path) if raw_path is not None else None,
        )
        return authorized_detail(self.context, {
            "metadata": details.metadata,
            "intelligence": {
                "context": details.intelligence.context.to_dict(),
                "explanation": details.intelligence.explanation.to_dict(),
                "limitation": details.limitation,
            },
        })

    def submit_review(self, row_id: int, status: str, reviewer_label: str,
                      notes: str | None = None):
        secure_path(self.feedback_db, root=self.trusted_root, must_exist=False)
        return submit_review(
            self.context, str(self.feedback_db), row_id, status, reviewer_label,
            notes, trusted_root=str(self.trusted_root),
            demonstration_path=str(self.demonstration_db) if self.demonstration_db is not None else None,
            production_only=self.production_only,
        )

    def feedback_summary(self) -> dict[str, Any]:
        return safe_feedback_summary(
            self.context, str(self.feedback_db), trusted_root=str(self.trusted_root),
            production_only=self.production_only,
            demonstration_path=str(self.demonstration_db) if self.demonstration_db is not None else None,
        )

    def diagnostics(self, cache: ScoreCache) -> dict[str, Any]:
        require_permission(self.context, "diagnostics.read")
        return {
            "validation_status": cache.validation_status,
            "architecture_version": cache.architecture_version,
            "threshold": cache.threshold,
            "transaction_count": cache.total_transactions,
            "alert_count": cache.alert_count,
            "source": "frozen score cache",
        }


def format_probability(value: float) -> str:
    """Format a validated probability for analyst-facing display only."""
    return f"{float(value):.2%}"


def alert_status_label(alert: bool) -> str:
    """Describe the existing frozen alert decision without adding categories."""
    return "Flagged for Investigation" if bool(alert) else "Not Flagged"


def risk_decision_explanation(probability: float, threshold: float, alert: bool) -> str:
    """Explain the stored decision using the stored score and threshold."""
    comparison = "exceeds" if bool(alert) else "does not exceed"
    return (
        f"The model estimates a fraud probability of {format_probability(probability)}. "
        f"This {comparison} the configured alert threshold of {format_probability(threshold)}, "
        f"so the transaction is {('flagged for investigation' if bool(alert) else 'not flagged')} "
        "by the frozen decision. This score does not establish that the transaction is fraudulent."
    )


def analyst_score_table(frame: pd.DataFrame) -> pd.DataFrame:
    """Create a readable table without changing the validated source frame."""
    display = frame.loc[:, [
        "row_id", "step", "fraud_probability", "baseline_anomaly_intensity",
        "behavioral_anomaly_intensity", "rule_score_context", "alert",
    ]].copy()
    display["fraud_probability"] = display["fraud_probability"].map(format_probability)
    display["alert"] = display["alert"].map(alert_status_label)
    return display.rename(columns={
        "row_id": "Transaction ID",
        "step": "Simulation Step",
        "fraud_probability": "Fraud Risk (%)",
        "baseline_anomaly_intensity": "Baseline Anomaly Indicator",
        "behavioral_anomaly_intensity": "Behavioral Anomaly Indicator",
        "rule_score_context": "Rule-Based Context",
        "alert": "Fraud Alert",
    })


def create_secure_dashboard(context: DashboardContext | None, **kwargs: Any) -> SecureDashboard:
    """Create the secure entry point; no context means immediate denial."""
    require_permission(context, "dashboard.read")
    return SecureDashboard(context, **kwargs)


def main(context: DashboardContext | None = None) -> SecureDashboard:
    """Controlled entry point for a future trusted Streamlit adapter.

    A normal launch with no trusted identity fails closed. Local tests may use
    ``issue_local_context`` explicitly, which is not suitable for deployment.
    """
    return create_secure_dashboard(context)


def _render_research_transparency(st: Any, cache: ScoreCache) -> None:
    """Render read-only provenance and limitations for the analyst demo."""
    provenance = FinalRiskAssessmentConfig()
    with st.expander("Research Transparency", expanded=False):
        st.markdown(
            "**Dataset disclosure:** This dashboard uses simulated PaySim "
            "transactions. Results are research benchmarks and do not establish "
            "real-world effectiveness, transferability, or production readiness."
        )
        st.markdown("**Model provenance**")
        st.markdown(
            f"- Frozen alert threshold: `{format_probability(provenance.fraud_alert_threshold)}`\n"
            f"- Threshold provenance: {provenance.threshold_provenance}\n"
            f"- Score-cache validation: `{cache.validation_status}` ({cache.total_transactions:,} rows)"
        )
        st.markdown(
            "**Validation methodology:** Scores and alerts are loaded from the "
            "frozen Module 4 holdout cache. The Random Forest probability drives "
            "alerts; anomaly intensities and rule context are independent "
            "indicators. No retraining or rescoring occurs in this dashboard."
        )


def _set_dashboard_section(section: str) -> None:
    """Navigate using session state without changing the selected transaction."""
    import streamlit as st

    st.session_state["dashboard_section"] = section


def _sync_widget_value(target_key: str, widget_key: str) -> None:
    """Persist a widget value after its widget leaves the active section."""
    import streamlit as st

    st.session_state[target_key] = st.session_state.get(widget_key)


def _render_navigation(st: Any, sections: tuple[str, ...]) -> str:
    """Render a compact, server-aware navigation control."""
    current = st.session_state.get("dashboard_section", sections[0])
    if current not in sections:
        current = sections[0]
        st.session_state["dashboard_section"] = current
    segmented_control = getattr(st, "segmented_control", None)
    if callable(segmented_control):
        if "dashboard_section" in st.session_state:
            selected = segmented_control("Dashboard section", sections, key="dashboard_section")
        else:
            selected = segmented_control("Dashboard section", sections, default=current, key="dashboard_section")
    else:
        if "dashboard_section" in st.session_state:
            selected = st.radio("Dashboard section", sections, horizontal=True, key="dashboard_section")
        else:
            selected = st.radio("Dashboard section", sections, index=sections.index(current), horizontal=True, key="dashboard_section")
    return str(selected or current)


def _render_overview(st: Any, cache: ScoreCache, safe_scores: pd.DataFrame) -> None:
    st.subheader("Overview")
    first, second, third = st.columns(3)
    first.metric("Total analyzed transactions", f"{len(safe_scores):,}")
    second.metric("Fraud alerts", f"{int(safe_scores['alert'].sum()):,}")
    third.metric("Alert percentage", f"{float(safe_scores['alert'].mean()):.2%}")
    charts = overview_aggregations(cache.frame)
    st.bar_chart(charts["probability_distribution"].set_index("probability_band"))
    st.line_chart(charts["alerts_by_step"].set_index("step")[["alerts", "alert_rate"]])
    _render_research_transparency(st, cache)


def _render_explorer(st: Any, context: DashboardContext, cache: ScoreCache) -> int | None:
    st.subheader("Transaction Explorer")
    controls = st.columns(4)
    step_min_value = controls[0].number_input(
        "Minimum step", min_value=378, max_value=743,
        value=int(st.session_state.get("explorer_step_min", 378)), step=1,
        key="widget_explorer_step_min", on_change=_sync_widget_value,
        args=("explorer_step_min", "widget_explorer_step_min"),
    )
    step_max_value = controls[1].number_input(
        "Maximum step", min_value=378, max_value=743,
        value=int(st.session_state.get("explorer_step_max", 743)), step=1,
        key="widget_explorer_step_max", on_change=_sync_widget_value,
        args=("explorer_step_max", "widget_explorer_step_max"),
    )
    alert_filter = controls[2].selectbox(
        "Alert status", ("All", "Alerted", "Not alerted"),
        index=("All", "Alerted", "Not alerted").index(st.session_state.get("explorer_alert_filter", "All")),
        key="widget_explorer_alert_filter", on_change=_sync_widget_value,
        args=("explorer_alert_filter", "widget_explorer_alert_filter"),
    )
    page_size_value = controls[3].selectbox(
        "Rows per page", (10, 25, 50, 100),
        index=(10, 25, 50, 100).index(int(st.session_state.get("explorer_page_size", 25))),
        key="widget_explorer_page_size", on_change=_sync_widget_value,
        args=("explorer_page_size", "widget_explorer_page_size"),
    )
    step_min = int(step_min_value)
    step_max = int(step_max_value)
    page_size = int(page_size_value)
    if step_min > step_max:
        st.error("Minimum step must not exceed maximum step.")
        return None
    alert_value = None if alert_filter == "All" else alert_filter == "Alerted"
    filtered = filter_scores(cache.frame, step_min=step_min, step_max=step_max, alert=alert_value)
    total_pages = max(1, (len(filtered) + page_size - 1) // page_size)
    if int(st.session_state.get("explorer_page", 1)) > total_pages:
        st.session_state["explorer_page"] = 1
    if int(st.session_state.get("widget_explorer_page", 1)) > total_pages:
        st.session_state["widget_explorer_page"] = 1
    page = int(st.number_input(
        "Page", min_value=1, max_value=total_pages,
        value=int(st.session_state.get("explorer_page", 1)), step=1,
        key="widget_explorer_page", on_change=_sync_widget_value,
        args=("explorer_page", "widget_explorer_page"),
    ))
    preview = paginate_scores(filtered, page=page, page_size=page_size)
    if preview.empty:
        st.info("No transactions match the current filters.")
        return None
    selected_options = [int(value) for value in preview["row_id"].tolist()]
    selected_transaction_id = st.session_state.get("selected_transaction_id")
    if selected_transaction_id not in selected_options:
        selected_transaction_id = None
        st.session_state["selected_transaction_id"] = None
    selection_options: list[int | None] = [None, *selected_options]
    if st.session_state.get("widget_selected_transaction") not in selection_options:
        st.session_state["widget_selected_transaction"] = selected_transaction_id
    selected_value = st.selectbox(
        "Selected transaction", selection_options,
        index=selection_options.index(selected_transaction_id),
        format_func=lambda value: "Select a transaction" if value is None else str(value),
        key="widget_selected_transaction", on_change=_sync_widget_value,
        args=("selected_transaction_id", "widget_selected_transaction"),
    )
    selected_row_id = int(selected_value) if selected_value is not None else None
    st.session_state["selected_transaction_id"] = selected_row_id
    display = analyst_score_table(authorized_scores(context, preview))
    display.insert(0, "Selected", display["Transaction ID"].eq(selected_row_id).map({True: "●", False: ""}))
    st.dataframe(display, height=420, use_container_width=True, hide_index=True)
    if selected_row_id is None:
        st.caption("No transaction selected. Choose a transaction to investigate.")
    else:
        st.caption(f"Selected transaction: {selected_row_id}. Details and feedback remain inside the authorized secure boundary.")
    st.button(
        "Investigate Selected Transaction",
        key="investigate_selected_transaction",
        on_click=_set_dashboard_section,
        args=("Transaction Details",),
        disabled=selected_row_id is None,
    )
    return selected_row_id


def _load_selected_details(st: Any, context: DashboardContext, dashboard: SecureDashboard,
                           cache: ScoreCache, selected_row_id: int) -> dict[str, Any] | None:
    """Load one authorized detail payload once per Streamlit session and row."""
    require_permission(context, "transaction.detail")
    context_key = (context.role, context.authenticated)
    if st.session_state.get("dashboard_context_key") != context_key:
        for key in ("transaction_details", "transaction_details_row_id", "dashboard_retrieval_index", "dashboard_metadata_index"):
            st.session_state.pop(key, None)
        st.session_state["dashboard_context_key"] = context_key
    if st.session_state.get("transaction_details_row_id") != selected_row_id:
        st.info("Select Load Transaction Details to retrieve the authorized metadata and intelligence for this transaction.")
        if not st.button("Load Transaction Details", key="load_transaction_details"):
            return None
        try:
            with st.spinner("Loading aligned transaction details and authoritative intelligence..."):
                retrieval_index = st.session_state.get("dashboard_retrieval_index")
                if retrieval_index is None:
                    retrieval_index = build_retrieval_index(AUTHORITATIVE_KB_PATH, expected_version=AUTHORITATIVE_KB_VERSION)
                    st.session_state["dashboard_retrieval_index"] = retrieval_index
                metadata_index = st.session_state.get("dashboard_metadata_index")
                if metadata_index is None:
                    metadata_index = load_metadata_index(METADATA_INDEX_PATH, PAYSIM_RAW_PATH, cache)
                    st.session_state["dashboard_metadata_index"] = metadata_index
                st.session_state["transaction_details"] = dashboard.load_transaction_detail(
                    selected_row_id, cache, retrieval_index, metadata_index=metadata_index
                )
                st.session_state["transaction_details_row_id"] = selected_row_id
        except (OSError, ValueError, AuthorizationError) as exc:
            st.error(f"Unable to load transaction details safely: {exc}")
            return None
    return st.session_state.get("transaction_details")


def _render_transaction_details(st: Any, details: dict[str, Any] | None) -> None:
    st.subheader("Transaction Details")
    if details is None:
        st.info("No transaction details are loaded. Select a transaction in Transaction Explorer and choose Investigate Selected Transaction.")
        return
    metadata = details.get("metadata", {})
    risk_context = details.get("intelligence", {}).get("context", {})
    summary = st.columns(6)
    summary[0].metric("Transaction ID", str(metadata.get("row_id", "Unavailable")))
    summary[1].metric("Transaction Type", str(metadata.get("type", "Unavailable")))
    summary[2].metric("Transaction Amount", f"{float(metadata.get('amount', 0.0)):,.2f} simulation units")
    summary[3].metric("Simulation Step", str(metadata.get("step", "Unavailable")))
    summary[4].metric("Fraud Risk Score", format_probability(risk_context.get("fraud_probability", 0.0)))
    summary[5].metric("Alert Status", alert_status_label(risk_context.get("alert", False)))
    st.subheader("Fraud Risk Assessment")
    risk_columns = st.columns(3)
    risk_columns[0].metric("Frozen Random Forest Probability", format_probability(risk_context.get("fraud_probability", 0.0)))
    risk_columns[1].metric("Frozen Alert Threshold", format_probability(risk_context.get("threshold", 0.0)))
    risk_columns[2].metric("Decision", alert_status_label(risk_context.get("alert", False)))
    st.write(risk_decision_explanation(risk_context.get("fraud_probability", 0.0), risk_context.get("threshold", 0.0), risk_context.get("alert", False)))
    st.subheader("Unusual Transaction Behavior")
    anomaly_columns = st.columns(3)
    anomaly_columns[0].metric("Baseline Anomaly Indicator", f"{float(risk_context.get('baseline_anomaly_intensity', 0.0)):.4f}")
    anomaly_columns[0].caption("Isolation Forest intensity from the baseline feature set; it is not a fraud probability.")
    anomaly_columns[1].metric("Behavioral Anomaly Indicator", f"{float(risk_context.get('behavioral_anomaly_intensity', 0.0)):.4f}")
    anomaly_columns[1].caption("Isolation Forest intensity using available behavioral features; it is not a fraud probability.")
    anomaly_columns[2].metric("Rule-Based Context", f"{float(risk_context.get('rule_score_context', 0.0)):.4f}")
    anomaly_columns[2].caption("Contextual rule signal. It does not override the frozen Random Forest alert decision.")


def _render_fraud_intelligence(st: Any, details: dict[str, Any] | None) -> None:
    st.subheader("Fraud Intelligence")
    if details is None:
        st.info("Load the selected transaction in Transaction Details to view authoritative fraud intelligence.")
        return
    intelligence = details.get("intelligence", {})
    explanation = intelligence.get("explanation", {})
    st.caption("Retrieved fraud intelligence provides investigative context and does not establish that a particular transaction is fraudulent.")
    evidence = explanation.get("retrieved_evidence", [])
    if evidence:
        for number, item in enumerate(evidence, start=1):
            if not isinstance(item, Mapping):
                continue
            with st.container(border=True):
                st.markdown(f"**Source {number}: {item.get('source_organization', 'Unavailable')}**")
                st.caption(f"Topic / document: {item.get('document_id', 'Unavailable')}")
                st.write(item.get("passage", "No passage was returned."))
                source_url = item.get("source_url")
                if isinstance(source_url, str) and source_url.startswith(("https://", "http://")):
                    st.link_button("Open authoritative source", source_url)
                elif source_url:
                    st.caption(f"Source locator: {source_url}")
    else:
        st.info("No relevant authoritative evidence met the existing retrieval cutoff for this transaction context.")
    st.subheader("Recommended Investigation Steps")
    suggested_steps = explanation.get("suggested_review_steps", [])
    if suggested_steps:
        for number, step in enumerate(suggested_steps, start=1):
            st.markdown(f"{number}. {step}")
    else:
        st.info("No additional investigation steps were returned for this transaction.")


def _render_analyst_review(st: Any, dashboard: SecureDashboard, selected_row_id: int | None,
                           details: dict[str, Any] | None) -> None:
    st.subheader("Analyst Review")
    if selected_row_id is None or details is None:
        st.info("Load the selected transaction in Transaction Details before recording an assessment.")
        return
    st.caption("Reviews are mutable analyst workflow information and are not verified fraud labels.")
    status = st.selectbox("Review status", REVIEW_STATUSES, key="review_status")
    notes = st.text_area("Investigation notes (not displayed after submission)", max_chars=4000, key="review_notes")
    if st.button("Save review", key="save_review"):
        try:
            dashboard.submit_review(selected_row_id, status, "local-analyst", notes or None)
            st.success("Review saved.")
        except (OSError, ValueError, AuthorizationError) as exc:
            st.error(f"Review was not saved: {exc}")
    try:
        summary = dashboard.feedback_summary()
        st.caption(f"Feedback events recorded: {summary['event_count']}")
    except (OSError, ValueError, AuthorizationError) as exc:
        st.error(f"Feedback summary unavailable: {exc}")


def streamlit_main(context: DashboardContext | None = None, *,
                   feedback_db: str | Path = FEEDBACK_DB_PATH,
                   demonstration_db: str | Path | None = None,
                   production_only: bool = True) -> None:
    """Run the supported Streamlit launcher with authorization first."""
    import streamlit as st

    st.set_page_config(page_title="Fraud Risk Analyst Dashboard (Secure)", layout="wide")
    if context is None:
        st.error("No trusted identity is configured. Protected dashboard access is denied.")
        return
    try:
        dashboard = create_secure_dashboard(context, feedback_db=feedback_db, demonstration_db=demonstration_db, production_only=production_only)
        require_permission(context, "dashboard.read")
        cache = load_score_cache()
        safe_scores = authorized_scores(context, cache.frame)
    except AuthorizationError as exc:
        st.error(str(exc))
        return
    except (OSError, ValueError) as exc:
        st.error(f"Dashboard data validation failed: {exc}")
        return

    st.title("Fraud Risk Analyst Dashboard")
    st.info("Research prototype using simulated PaySim data. Frozen scores and alerts are read-only.")
    sections = ("Overview", "Transaction Explorer", "Transaction Details", "Fraud Intelligence", "Analyst Review")
    selected_section = _render_navigation(st, sections)
    selected_row_id: int | None = st.session_state.get("selected_transaction_id")
    if selected_section == "Overview":
        _render_overview(st, cache, safe_scores)
    elif selected_section == "Transaction Explorer":
        selected_row_id = _render_explorer(st, context, cache)
    else:
        if selected_row_id is None:
            st.info("No transaction is selected. Open Transaction Explorer to choose one.")
        details = None
        if selected_row_id is not None:
            details = _load_selected_details(st, context, dashboard, cache, int(selected_row_id))
        if selected_section == "Transaction Details":
            _render_transaction_details(st, details)
        elif selected_section == "Fraud Intelligence":
            _render_fraud_intelligence(st, details)
        else:
            _render_analyst_review(st, dashboard, selected_row_id, details)


__all__ = ["AuthorizationError", "SecureDashboard", "create_secure_dashboard", "main", "streamlit_main"]
