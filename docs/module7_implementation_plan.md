# Module 7 Implementation Plan

## Stage 1 — Architecture and contracts

Define and review the contracts in `module7_stage1_data_contracts.md`; inspect frozen schemas and publish the issue register. Validation is documentation-level and lightweight.

## Stage 2 — Transaction, alert, and score monitoring

Build read-only streaming/column-bounded summaries from the score cache and metadata sidecar. Produce versioned JSON summaries for counts, alert rates, score distributions, anomaly distributions, missingness, and transaction types. Test exact counts against fixtures, immutability, complete-step boundaries, and reproducibility. This stage is low-to-moderate cost and does not require raw CSV scans when the sidecar is sufficient.

## Stage 3 — Data and prediction drift

Implement predeclared reference/current windows and PSI, KS, Jensen–Shannon, and missingness comparisons with sample-size warnings. Keep thresholds in a versioned monitoring configuration rather than tuning against final-holdout labels. Test deterministic output, insufficient samples, categorical support changes, and no mutation of frozen inputs.

## Stage 4 — Analyst feedback analysis

Read the clean production-like SQLite database read-only and summarize activity, statuses, backlog, and time trends. Preserve demonstration data separation. Test database corruption, missing databases, event ordering, and the rule that statuses are not labels.

## Stage 5 — Experiment tracking and reproducibility

Publish append-only run manifests with source hashes, code hashes, package versions, window definitions, metrics, warnings, and output checksums. A lightweight JSON manifest is preferred to installing MLflow on the constrained local prototype.

## Stage 6 — Controlled retraining and governance design

Design approval gates, independent labels, temporal splits, model comparison, threshold governance, rollback, and artifact promotion. No retraining or threshold change occurs automatically.

## Stage 7 — End-to-end validation and Module 7 V1 freeze

Validate the complete read-only run, failure recovery, deterministic reports, resource use, and artifact immutability. Freeze only after review of limitations and evidence. Future monitoring outputs remain separate from Module 4–6 historical results.

