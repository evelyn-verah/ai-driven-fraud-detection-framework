# Module 7 Stage 1: Monitoring Architecture

## Scope and operating mode

Module 7 begins as a read-only monitoring subsystem for the frozen Module 4, Module 5, and Module 6 V1 research artifacts. It reads existing score caches, the validated metadata sidecar, the authoritative knowledge-base manifest, and analyst feedback. It does not alter scores, thresholds, model files, knowledge-base files, the sidecar, or historical evaluation reports.

PaySim is simulated mobile-money data. Monitoring findings are descriptive research outputs and do not establish fraud prevention, production deployment, or regulatory compliance.

## Data flow

`Frozen artifact readers -> validated monitoring records -> time-window/reference resolver -> metric calculators -> drift and finding records -> append-only monitoring report`

The readers reuse `src/dashboard/data_access.py`, `src/dashboard/metadata_index.py`, `src/dashboard/feedback_store.py`, and the Module 4/5 manifests. Monitoring outputs are written to a new versioned Module 7 artifact directory. No output is written beneath the frozen Module 4, Module 5, or Module 6 artifact paths.

## Components

### Module 7 V1

- Read-only integrity validation for score cache, sidecar, and dependency manifests.
- Transaction, alert, score, and anomaly summaries from precomputed fields.
- Explicit reference-period and current-period contracts with complete-step boundaries.
- Descriptive categorical and continuous distribution comparisons.
- Missingness and volume checks.
- Analyst feedback counts and status distributions, without treating statuses as labels.
- Versioned monitoring run metadata and findings with source provenance.
- Deterministic JSON/Parquet outputs suitable for a 16 GB Windows laptop.

### Deferred enhancements

- Delayed-label performance evaluation, available only after an independently verified label source is aligned.
- Production alerting, service orchestration, access control, and multi-user feedback.
- MLflow or another experiment tracker; a manifest-based tracker is sufficient for V1.
- Controlled retraining and model approval workflows.
- Online or streaming monitoring.

## Reference periods

The original temporal partitions remain immutable: training 1–36, early validation 37–41, diagnostic 42–45, calibration 46–200, development evaluation 201–377, and final holdout 378–743. V1 may use completed historical steps for retrospective descriptive comparisons, but reference selection must be documented before metrics are inspected. Final-holdout labels and outcomes must not tune drift thresholds, recalibrate the frozen threshold, or select a model.

Monitoring windows use complete PaySim steps only. A run records the source artifact versions, step bounds, row counts, and selection rationale.

## Governance controls

- Require manifest and checksum validation before reading immutable inputs.
- Keep the frozen threshold and alert decisions read-only.
- Never use `isFraud` or `isFlaggedFraud` as a predictive monitoring feature.
- Treat analyst statuses as opinions, not verified labels.
- Keep monitoring results in a new versioned directory and never overwrite prior runs.
- Require independent verified labels before delayed-label metrics.
- Record model, architecture, threshold, source, and code versions in every run.
- Report drift as a distribution change; drift alone does not prove model degradation or fraud increase.

