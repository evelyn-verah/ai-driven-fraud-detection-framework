# Module 6 Post-Freeze Issue Register

## M6-001 — Ground-truth label exposed in Transaction Explorer

**Status:** Resolved in Module 6 V1.1; historical V1 retained unchanged as evidence.

`src/dashboard/config.py` defines `SCORE_COLUMNS` with `isFraud`. `filter_scores()` and `paginate_scores()` preserve all score columns, and `src/dashboard/app.py` passes the resulting `preview` directly to `st.dataframe()`. Therefore the explorer table can display the PaySim ground-truth `isFraud` column to an analyst. The details view does not include the label in its displayed metadata and explains that the label is used only for internal alignment, but the explorer exposure is a research-integrity defect.

**Impact:** An analyst can see the evaluation label, and it could influence review behavior. This does not change model scores, but it compromises the intended analyst-facing separation between predictions and labels.

**Resolution:** Module 6 V1.1 now uses an explicit analyst-safe display-column projection while retaining `isFraud` only inside validated alignment code. Regression tests verify that the projection excludes labels and account identifiers. The historical V1 manifest was not modified; a byte-for-byte source snapshot and separate V1.1 maintenance manifest are recorded under `artifacts/module6_v1_1/`.

## M6-002 — Demonstration reviewer label and feedback isolation

**Status:** Controlled, with a documented limitation.

The app configuration targets `artifacts/module6_feedback/production_reviews.sqlite3`. The Stage 5 demonstration events, including reviewer label `stage5-demo`, remain in the separate `reviews.sqlite3` database and are not read by the clean workflow. The SQLite schema accepts arbitrary bounded reviewer labels, so a user could manually enter `stage5-demo`; this is a label namespace concern rather than leakage of the preserved demonstration rows.

**Recommendation:** Keep the separate database paths, document reviewer-label conventions, and consider a future deployment-specific namespace or authenticated reviewer identity. No database migration or deletion is appropriate in Stage 1.

## Freeze impact

These findings do not silently change the Module 6 V1 manifest or frozen Module 4/5 artifacts. M6-001 is resolved in the reviewed V1.1 working-tree maintenance version. Module 7 monitoring must treat Module 6 outputs as frozen historical inputs and must not use `isFraud` in analyst-facing summaries.
