# Module 7 Stage 4 — Analyst feedback analysis

Stage 4 provides a read-only, reproducible summary of Module 6 review activity. It does not write SQLite tables, alter review history, modify frozen risk scores, or treat analyst assessments as verified fraud labels.

## Data contract and access

The source is `artifacts/module6_feedback/production_reviews.sqlite3`; the demonstration database is never selected by default. The existing `review_events` table is append-only and contains `event_id`, non-negative holdout-relative `row_id`, one of the five existing review statuses, reviewer label, optional notes, and an ISO-8601 `created_at_utc` value. The analyzer opens SQLite in read-only URI mode, validates the required schema/statuses/timezone, and uses one read-only connection for a consistent snapshot. It never exposes reviewer labels or notes and does not persist a database checksum as immutable provenance because the database is mutable; file size, modification time, and snapshot strategy are recorded instead.

## Metrics

The JSON summary separates event counts from distinct reviewed transaction counts. It reports status counts/proportions, escalation count, reviews per transaction, repeat-review events and transactions, activity by UTC date, optional UTC time-window filtering, and latest-status distribution. Latest status is a descriptive current workflow state, not a final investigation outcome. No response-time or productivity measure is inferred.

When the frozen score cache is supplied, reviewed row IDs are joined read-only to stored fraud probabilities and alert decisions. The output reports aligned versus missing score events, alerted/non-alerted event counts, fixed probability risk bands, status distributions by band, escalation counts by band, and the unchanged frozen threshold. It does not recalculate predictions or include `isFraud`, account identifiers, reviewer names, or notes.

## Validation

Synthetic SQLite tests cover missing and empty databases, malformed schemas, status counts, repeated reviews, latest-status logic, UTC dates/windows, alerted/non-alerted alignment, risk bands, missing score IDs, output privacy, database immutability, deterministic summaries, and demonstration-database separation. The complete project suite passed 127 tests before Stage 4 and the Stage 4-focused suite adds 8 tests.

The clean production-like database was read without modification. It currently contains **0 review events** and **0 distinct reviewed transactions**. The read completed in approximately 0.011 seconds. The resulting empty summary is [production_feedback_summary.json](../artifacts/module7_stage4_feedback/production_feedback_summary.json).

## Limitations and reproduction

Feedback is workflow data for a local research prototype over simulated PaySim transactions. Statuses such as `False Positive Suspected` and `Escalated` are human assessments/actions, not independently verified outcomes. Empty or inaccessible databases are reported without fabricating activity; malformed schemas fail safely. Future stages may analyze feedback quality or governance, but must not use it as a training label without an independent verification process.

Run `python -m pytest tests/test_monitoring_stage4.py` for focused validation. Use `analyze_feedback()` with its default production path, optionally passing an already validated score frame, and publish with `write_monitoring_result`.
