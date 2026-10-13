"""Module 6 V1.2 secure dashboard execution boundary.

This entry point is intentionally separate from the historical Streamlit
application. It accepts only an already-issued Stage 4 context; it never
turns a URL, widget, or role string into an authenticated identity.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from src.dashboard.config import (
    AUTHORITATIVE_KB_PATH,
    AUTHORITATIVE_KB_VERSION,
    FEEDBACK_DB_PATH,
    METADATA_INDEX_PATH,
    PAYSIM_RAW_PATH,
    ROOT,
    SCORE_CACHE_PATH,
)
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
                 feedback_db: str | Path = FEEDBACK_DB_PATH) -> None:
        self.context = context
        self.trusted_root = Path(trusted_root)
        self.feedback_db = Path(feedback_db)

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
        )

    def feedback_summary(self) -> dict[str, Any]:
        return safe_feedback_summary(
            self.context, str(self.feedback_db), trusted_root=str(self.trusted_root),
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


def streamlit_main(context: DashboardContext | None = None) -> None:
    """Run the supported Streamlit launcher with authorization first.

    Normal launches have no trusted identity and therefore render only a
    denial message. A future identity-provider adapter may call this function
    with a verified context; role widgets and URL parameters are never used.
    """
    import streamlit as st

    st.set_page_config(page_title="Fraud Risk Analyst Dashboard (Secure)", layout="wide")
    if context is None:
        st.error("No trusted identity is configured. Protected dashboard access is denied.")
        return
    try:
        dashboard = create_secure_dashboard(context)
        require_permission(context, "dashboard.read")
        cache = load_score_cache()
        safe_scores = authorized_scores(context, cache.frame)
    except AuthorizationError as exc:
        st.error(str(exc))
        return
    except (OSError, ValueError) as exc:
        st.error(f"Dashboard data validation failed: {exc}")
        return

    st.title("Fraud Risk Analyst Dashboard (Secure V1.2)")
    st.info("Research prototype using simulated PaySim data. Frozen scores and alerts are read-only.")
    first, second, third = st.columns(3)
    first.metric("Total analyzed transactions", f"{len(safe_scores):,}")
    second.metric("Alerts", f"{int(safe_scores['alert'].sum()):,}")
    third.metric("Alert percentage", f"{float(safe_scores['alert'].mean()):.2%}")

    charts = overview_aggregations(cache.frame)
    st.subheader("Overview")
    st.bar_chart(charts["probability_distribution"].set_index("probability_band"))
    st.line_chart(charts["alerts_by_step"].set_index("step")[["alerts", "alert_rate"]])

    st.subheader("Transaction Explorer")
    controls = st.columns(4)
    step_min = controls[0].number_input("Minimum step", min_value=378, max_value=743, value=378, step=1)
    step_max = controls[1].number_input("Maximum step", min_value=378, max_value=743, value=743, step=1)
    alert_filter = controls[2].selectbox("Alert status", ("All", "Alerted", "Not alerted"))
    page_size = controls[3].selectbox("Rows per page", (10, 25, 50, 100), index=1)
    if step_min > step_max:
        st.error("Minimum step must not exceed maximum step.")
        return
    alert_value = None if alert_filter == "All" else alert_filter == "Alerted"
    filtered = filter_scores(cache.frame, step_min=int(step_min), step_max=int(step_max), alert=alert_value)
    total_pages = max(1, (len(filtered) + int(page_size) - 1) // int(page_size))
    page = st.number_input("Page", min_value=1, max_value=total_pages, value=1, step=1)
    preview = paginate_scores(filtered, page=int(page), page_size=int(page_size))
    st.dataframe(authorized_scores(context, preview), use_container_width=True, hide_index=True)
    if preview.empty:
        return
    selected_row_id = st.selectbox("Select a transaction", preview["row_id"].tolist())
    st.caption("Transaction details and feedback are available only through the authorized secure boundary.")
    if st.button("Load aligned metadata and authoritative intelligence"):
        try:
            retrieval_index = build_retrieval_index(
                AUTHORITATIVE_KB_PATH, expected_version=AUTHORITATIVE_KB_VERSION
            )
            metadata_index = load_metadata_index(METADATA_INDEX_PATH, PAYSIM_RAW_PATH, cache)
            st.session_state["transaction_details"] = dashboard.load_transaction_detail(
                int(selected_row_id), cache, retrieval_index, metadata_index=metadata_index
            )
            st.session_state["transaction_details_row_id"] = int(selected_row_id)
        except (OSError, ValueError) as exc:
            st.error(f"Unable to load transaction details safely: {exc}")
    details = st.session_state.get("transaction_details")
    if details is not None and st.session_state.get("transaction_details_row_id") == int(selected_row_id):
        st.json(details)
        st.subheader("Analyst review")
        st.caption("Reviews are mutable analyst workflow information and are not verified fraud labels.")
        status = st.selectbox("Review status", REVIEW_STATUSES)
        notes = st.text_area("Investigation notes (not displayed after submission)", max_chars=4000)
        if st.button("Save review"):
            try:
                dashboard.submit_review(int(selected_row_id), status, "local-analyst", notes or None)
                st.success("Review saved.")
            except (OSError, ValueError, AuthorizationError) as exc:
                st.error(f"Review was not saved: {exc}")
        try:
            summary = dashboard.feedback_summary()
            st.caption(f"Feedback events recorded: {summary['event_count']}")
        except (OSError, ValueError, AuthorizationError) as exc:
            st.error(f"Feedback summary unavailable: {exc}")


__all__ = ["AuthorizationError", "SecureDashboard", "create_secure_dashboard", "main", "streamlit_main"]
