# Module 6 Stage 1: Dashboard architecture plan

## Scope

The dashboard will be a local Streamlit research prototype over the completed Module 4 holdout score cache and the frozen Module 5 intelligence layer. It will never invoke model fitting, rescoring, threshold selection, or automatic retraining.

## Frozen inputs and join contract

The primary score source is `artifacts/module4_final_holdout_recovery_v1/complete_holdout_scores.csv`. It contains 955,744 rows for steps 378–743 with `row_id`, `step`, `isFraud`, Random Forest probability, two anomaly intensities, rule score context, and the frozen alert decision. `row_id` is a holdout-relative sequential identifier: the recovery code assigns it from zero at step 378 and validates alignment by chronological step order and source labels. It is not a raw CSV line number or pandas index.

The dashboard will load score columns with compact dtypes and cache the resulting frame. Original PaySim metadata will be joined on demand by scanning the raw CSV in chronological complete steps, maintaining the same holdout-relative row counter and selecting only requested IDs. The join service will verify step, within-step order, row counts, and labels against the score cache before returning metadata. No six-million-row frame will be retained. A later optimization may build a local step-offset sidecar, but it is not required for the minimal prototype.

## Proposed files

- `src/dashboard/app.py`: Streamlit entry point and five-area navigation.
- `src/dashboard/data_access.py`: read-only score loading, bounded raw metadata lookup, schema and alignment checks, and pagination.
- `src/dashboard/feedback_store.py`: separate analyst review persistence with atomic JSONL writes and input validation.
- `src/dashboard/config.py`: paths, frozen architecture identifiers, and display limits.
- `tests/test_dashboard_data_access.py` and `tests/test_dashboard_feedback.py`: fixture-based tests without loading the full PaySim file.
- `artifacts/module6_feedback/`: mutable analyst notes and review state, excluded from frozen research artifacts.

## Page layout

1. **Overview**: transaction and alert counts, alert percentage, probability histogram, transaction-type distribution from bounded metadata aggregation, and step-level alert trend.
2. **Transaction Explorer**: filters for step range, alert, probability range, and transaction type; stable pagination over the score cache; no raw identifiers in default prose.
3. **Transaction Details**: selected score record, aligned PaySim metadata, anomaly indicators clearly labeled as non-probabilistic, rule context, Module 5 retrieval, citations, grounded explanation, and limitations.
4. **Analyst Review**: review status and notes stored separately from score data. Saving a note cannot change a score, alert, threshold, or model artifact.
5. **Research and Transparency**: PaySim disclosure, development and holdout metrics, architecture and threshold provenance, model versions, retrieval KB version, and prototype limitations.

## Module 4 and Module 5 integration

The dashboard will read score records and use the existing Module 5 adapter. It will supply only metadata actually retrieved from PaySim, preserve all numeric values exactly, build the deterministic query from the validated context, call the read-only authoritative retrieval index, and generate the existing grounded explanation. Missing metadata will produce a visible validation state rather than fabricated defaults. Retrieved content remains untrusted evidence and cannot alter scores or alert decisions.

## Feedback and safety

Feedback records will contain a generated review key, row_id, reviewer label, bounded note text, status, and UTC timestamp. The store will use atomic replacement or append-only JSONL with schema validation, length limits, control-character rejection, and no sender/receiver identifiers in prose. Feedback is not used for retraining in this prototype. The app will run locally, avoid network calls, and display source URLs only as provenance links.

## Dependencies

`streamlit` is importable in the selected Python 3.13 environment but is not declared in `requirements.txt`; it should be added only when implementation is approved. Pandas, NumPy, scikit-learn, and PyArrow are available. Plotly and DuckDB are not installed and are unnecessary for the minimal version; Streamlit built-in charts and pandas summaries are sufficient.

## Staged implementation

1. Add read-only configuration, score-cache loader, schema checks, and bounded metadata join; test row alignment and memory-safe pagination on fixtures.
2. Add feedback store and validation tests.
3. Build the Overview and Explorer views from precomputed scores.
4. Add details view with Module 5 authoritative retrieval and explanation.
5. Add transparency and analyst-review views, then run an offline smoke test and full suite.
6. Optionally add a sidecar step-offset index only if measured lookup latency requires it.

## Decisions and blockers

No architecture blocker remains. Implementation approval is required before adding Streamlit files or declaring the dependency. The main operational decision is whether to persist the optional raw-step offset sidecar; the minimal implementation should defer it until lookup profiling demonstrates a need.
