"""Local Streamlit fraud-risk dashboard with analyst review capture."""

from __future__ import annotations

import streamlit as st

from src.dashboard.config import AUTHORITATIVE_KB_PATH, AUTHORITATIVE_KB_VERSION, DEFAULT_PAGE_SIZE, SCORE_CACHE_PATH, METADATA_INDEX_PATH, PAYSIM_RAW_PATH, FEEDBACK_DB_PATH
from src.dashboard.data_access import DataValidationError, filter_scores, load_score_cache, overview_aggregations, paginate_scores
from src.dashboard.details import build_transaction_details
from src.dashboard.metadata_index import load_metadata_index
from src.dashboard.feedback_store import REVIEW_STATUSES, latest_review, review_history, save_review
from src.fraud_intelligence.retrieval import build_retrieval_index


@st.cache_data(show_spinner=False)
def _cached_score_data():
    return load_score_cache()


@st.cache_resource(show_spinner=False)
def _cached_retrieval_index():
    return build_retrieval_index(AUTHORITATIVE_KB_PATH, expected_version=AUTHORITATIVE_KB_VERSION)


@st.cache_resource(show_spinner=False)
def _cached_metadata_index():
    if not METADATA_INDEX_PATH.is_dir():
        return None
    return load_metadata_index(METADATA_INDEX_PATH, PAYSIM_RAW_PATH, load_score_cache())


def main() -> None:
    st.set_page_config(page_title="Fraud Risk Analyst Dashboard", layout="wide")
    st.title("Fraud Risk Analyst Dashboard")
    st.info("Research prototype using simulated PaySim data. Module 4 scores and alerts are frozen; this shell does not rescore or retrain models.")
    try:
        cache = _cached_score_data()
    except (DataValidationError, FileNotFoundError, OSError) as exc:
        st.error(f"Score-cache validation failed: {exc}")
        st.stop()
    st.success(f"Score cache validated: {SCORE_CACHE_PATH.name}")
    first, second, third = st.columns(3)
    first.metric("Total analyzed transactions", f"{cache.total_transactions:,}")
    second.metric("Alerts", f"{cache.alert_count:,}")
    third.metric("Alert percentage", f"{cache.alert_count / cache.total_transactions:.2%}")
    st.caption("PaySim is simulated data. Anomaly intensities are independent indicators; they are not fraud probabilities and do not change the frozen Random Forest alert decision.")

    overview = st.container()
    with overview:
        st.subheader("Overview")
        charts = overview_aggregations(cache.frame)
        st.caption("Fraud-probability distribution")
        st.bar_chart(charts["probability_distribution"].set_index("probability_band"))
        st.caption("Alerts and alert rate by PaySim simulation step")
        st.line_chart(charts["alerts_by_step"].set_index("step")[["alerts", "alert_rate"]])
        st.caption("Mean anomaly intensity by score band; higher intensity means more anomalous, not more probable fraud")
        st.line_chart(charts["anomaly_distribution"].set_index("band"))

    st.subheader("Transaction Explorer")
    controls = st.columns(5)
    step_min = controls[0].number_input("Minimum step", min_value=378, max_value=743, value=378, step=1)
    step_max = controls[1].number_input("Maximum step", min_value=378, max_value=743, value=743, step=1)
    alert_filter = controls[2].selectbox("Alert status", ("All", "Alerted", "Not alerted"))
    probability_min, probability_max = controls[3].slider("Fraud probability", 0.0, 1.0, (0.0, 1.0), 0.01)
    page_size = controls[4].selectbox("Rows per page", (10, 25, 50, 100), index=1)
    if step_min > step_max:
        st.error("Minimum step must not exceed maximum step.")
        st.stop()
    alert_value = None if alert_filter == "All" else alert_filter == "Alerted"
    filtered = filter_scores(
        cache.frame, step_min=int(step_min), step_max=int(step_max), alert=alert_value,
        probability_min=float(probability_min), probability_max=float(probability_max),
    )
    row_search = st.text_input("Search holdout-relative row_id (optional)", value="")
    if row_search.strip():
        try:
            searched_id = int(row_search)
        except ValueError:
            st.error("row_id search must be an integer.")
            st.stop()
        if not 0 <= searched_id <= 955743:
            st.error("row_id search is outside the frozen holdout range.")
            st.stop()
        filtered = filtered.loc[filtered["row_id"] == searched_id].reset_index(drop=True)
    total_pages = max(1, (len(filtered) + int(page_size) - 1) // int(page_size))
    page = st.number_input("Page", min_value=1, max_value=total_pages, value=1, step=1)
    preview = paginate_scores(filtered, page=int(page), page_size=int(page_size))
    st.caption(f"{len(filtered):,} matching transactions; page {int(page)} of {total_pages}. Row IDs remain holdout-relative and stable.")
    st.dataframe(preview, use_container_width=True, hide_index=True)
    if not preview.empty:
        selected_row_id = st.selectbox("Select a transaction for details", preview["row_id"].tolist())
        selected = preview.loc[preview["row_id"] == selected_row_id].iloc[0]
        st.write({
            "row_id": int(selected["row_id"]),
            "step": int(selected["step"]),
            "fraud_probability": float(selected["fraud_probability"]),
            "alert": bool(selected["alert"]),
            "alert_threshold": cache.threshold,
        })
        st.subheader("Transaction Details and Fraud Intelligence")
        st.caption("Details are loaded only for the selected row. The true fraud label is retained for internal alignment validation and is never displayed or used in retrieval.")
        if st.button("Load aligned metadata and authoritative intelligence"):
            try:
                index = _cached_retrieval_index()
                metadata_index = _cached_metadata_index()
                st.session_state["transaction_details"] = build_transaction_details(int(selected_row_id), cache, index, metadata_index=metadata_index)
                st.session_state["transaction_details_row_id"] = int(selected_row_id)
            except (DataValidationError, FileNotFoundError, ValueError, OSError) as exc:
                st.session_state.pop("transaction_details", None)
                st.error(f"Unable to load transaction details safely: {exc}")
        details = st.session_state.get("transaction_details")
        if details is not None and st.session_state.get("transaction_details_row_id") == int(selected_row_id):
            context = details.intelligence.context
            st.markdown("**Observed transaction facts**")
            st.json(details.metadata)
            st.markdown("**Frozen Module 4 risk indicators**")
            st.json({
                "fraud_probability": context.fraud_probability,
                "alert": context.alert,
                "frozen_threshold": context.threshold,
                "baseline_anomaly_intensity": context.baseline_anomaly_intensity,
                "behavioral_anomaly_intensity": context.behavioral_anomaly_intensity,
                "rule_score_context": context.rule_score_context,
                "anomaly_note": "Anomaly intensities are contextual indicators, not fraud probabilities.",
            })
            st.markdown("**Evidence-grounded explanation**")
            explanation = details.intelligence.explanation
            for heading, values in (
                ("Observed facts", explanation.observed_facts),
                ("Model indicators", explanation.model_indicators),
                ("Possible interpretations", explanation.possible_interpretations),
                ("Uncertainty and limitations", explanation.uncertainty_and_limitations),
                ("Suggested analyst review steps", explanation.suggested_review_steps),
            ):
                st.markdown(f"*{heading}*")
                for value in values:
                    st.write(f"- {value}")
            st.markdown("**Retrieved authoritative evidence**")
            if not explanation.retrieved_evidence:
                st.info("No authoritative evidence met the retrieval relevance cutoff.")
            else:
                index = _cached_retrieval_index()
                for evidence in explanation.retrieved_evidence:
                    title = index.documents[evidence.document_id].title
                    st.write({
                        "document_id": evidence.document_id,
                        "title": title,
                        "source_url": evidence.source_url,
                        "knowledge_base_version": evidence.knowledge_base_version,
                        "retrieval_score": evidence.retrieval_score,
                        "passage": evidence.passage,
                    })
            st.caption(details.limitation)
            st.markdown("**Analyst review**")
            st.caption("Review assessments are local analyst notes and are not verified fraud labels. They do not change frozen scores or alerts.")
            if saved_at := st.session_state.pop("review_saved_at", None):
                st.success(f"Review saved at {saved_at} UTC.")
            current_review = latest_review(FEEDBACK_DB_PATH, int(selected_row_id))
            if current_review is None:
                st.info("No review has been recorded for this transaction.")
            else:
                st.write({"current_status": current_review.status, "reviewer": current_review.reviewer_label, "last_updated_utc": current_review.created_at_utc})
            with st.form(f"review_form_{int(selected_row_id)}", clear_on_submit=False):
                default_status = current_review.status if current_review is not None else "Unreviewed"
                review_status = st.selectbox("Review status", REVIEW_STATUSES, index=REVIEW_STATUSES.index(default_status))
                reviewer_label = st.text_input("Reviewer label", value=current_review.reviewer_label if current_review else "")
                notes = st.text_area("Investigation notes (optional)", value=current_review.notes or "" if current_review else "", max_chars=4000)
                submitted = st.form_submit_button("Save review")
            if submitted:
                try:
                    event = save_review(FEEDBACK_DB_PATH, int(selected_row_id), review_status, reviewer_label, notes or None)
                    st.session_state["review_saved_at"] = event.created_at_utc
                    st.rerun()
                except (ValueError, OSError) as exc:
                    st.error(f"Review was not saved: {exc}")
            history = review_history(FEEDBACK_DB_PATH, int(selected_row_id))
            if history:
                st.markdown("*Review history*")
                st.dataframe([
                    {"event_id": event.event_id, "status": event.status, "reviewer": event.reviewer_label, "notes": event.notes or "", "created_at_utc": event.created_at_utc}
                    for event in history
                ], use_container_width=True, hide_index=True)
    st.caption("Sender and receiver identifiers remain withheld. Reviews are stored locally as analyst assessments; monitoring is deferred to a later stage.")


if __name__ == "__main__":
    main()
