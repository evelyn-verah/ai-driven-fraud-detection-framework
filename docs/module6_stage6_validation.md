# Module 6 Stage 6: End-to-End Validation

Module 6 V1 is frozen as a local Streamlit research prototype over simulated PaySim transactions. The dashboard reads the frozen Module 4 holdout score cache, the validated metadata sidecar, and the read-only Module 5 authoritative knowledge base. It does not retrain, rescore, recalibrate, or write to those artifacts. The formal freeze manifest is [module6_v1_freeze_manifest.json](../artifacts/module6_v1_freeze_manifest.json).

## Validated data flow

1. `load_score_cache()` validates 955,744 holdout rows, frozen score ranges, sequential holdout-relative IDs, chronological steps, and threshold-derived alert decisions.
2. `load_metadata_index()` validates the source SHA-256, Parquet checksum, schema, row count, complete step coverage, row IDs, and internal step/label alignment.
3. The explorer filters and paginates the score frame without changing stored values.
4. A selected row is joined to the sidecar on holdout-relative `row_id`; raw sender and receiver identifiers are not loaded into the details view.
5. The Module 5 authoritative index produces traceable evidence and grounded explanations. Retrieved passages are contextual evidence, not proof of fraud.
6. Analyst reviews are appended to a separate SQLite database under `artifacts/module6_feedback/`.

## Review storage

`production_reviews.sqlite3` contains `review_events(event_id, row_id, status, reviewer_label, notes, created_at_utc)`. Events are append-only and latest status is derived by timestamp/event ID. The database stores no PaySim labels, model scores, sender/receiver identifiers, or retrieved passages. The original `reviews.sqlite3` Stage 5 row-0 demonstration remains unchanged and is excluded from the production-like review path.

## Validation and performance

- Full suite: 110 passed.
- Streamlit detached launch: health endpoint returned HTTP 200; browser rendering and row selection were exercised.
- Score cache: 955,744 transactions, steps 378–743, frozen alert threshold preserved.
- Sidecar: checksum and alignment validation passed.
- Cold score-cache load: approximately 1.53 s.
- Cold sidecar load: approximately 1.52 s.
- Cold authoritative retrieval-index build: approximately 0.09 s.
- Warm details load: approximately 0.0055 s for row 0 and 0.0034 s for the final row.
- Warm sidecar lookup: approximately 0.0004 s.
- Feedback save/read: approximately 0.050/0.003 s.

Failure paths for missing/corrupt sidecars, missing knowledge bases, invalid IDs and review inputs, SQLite write failures, and read-only artifact behavior are covered by focused tests and validation commands. No frozen Module 4 or Module 5 file changed during validation.

## Limitations

The application is local and single-user; SQLite feedback is not a multi-user service. The knowledge base uses curated government-source summaries and deterministic lexical retrieval. PaySim is simulated data, and the prototype has no production financial-institution deployment evidence. Persisted holdout scores do not contain per-transaction rule IDs or behavioral feature columns, so those fields remain explicitly unavailable.

Module 4 and Module 5 evaluation results are historical frozen research results. Analyst feedback remains mutable and is excluded from the freeze. Future monitoring, retraining, and operational security work belongs to later modules.
