# Implementation Status

## Module 8 Stage 6 — Final security validation and V1 freeze (complete)

Independently validated the supported ingestion, secure dashboard launcher,
authorization facade, SQLite/filesystem boundaries, trusted model loaders, and
monitoring integrity controls. Added
[test_module8_stage6_final_security.py](tests/test_module8_stage6_final_security.py).
The Stage 6 matrix passed **113 tests with 1 skip** and the full suite passed
**211 tests with 1 skip**. Module 4–7 frozen artifacts and historical manifests
retain their recorded SHA-256 values; no model retraining, rescoring, threshold
change, or monitoring rewrite occurred.

Module 8 is frozen as the research-prototype release
`module8_v1_frozen` in
[module8_v1_freeze_manifest.json](artifacts/module8_v1_freeze_manifest.json).
Final validation and explicit severity-classified limitations are documented in
[module8_v1_final_security_validation.md](docs/module8_v1_final_security_validation.md)
and [module8_v1_security_limitations.md](docs/module8_v1_security_limitations.md).
This is not production security certification; authentication, signed sessions,
managed RBAC, authenticated artifact provenance, dependency locking, and
symlink-capable CI remain deployment requirements.

## Module 4 trusted model-loading security maintenance (complete)

Added [trusted_artifacts.py](src/risk_engine/trusted_artifacts.py) with
source-controlled role/path/SHA-256 anchors matching the frozen Module 4
recovery manifest. Updated [final_architecture.py](src/risk_engine/final_architecture.py)
and [run_development_evaluation.py](src/risk_engine/run_development_evaluation.py)
to verify exact frozen artifacts before deserialization. Original source hashes
and trusted model checksums are recorded in
[module4_trusted_model_loading_maintenance_manifest.json](artifacts/module4_trusted_model_loading_maintenance_manifest.json).
Focused risk/security regressions pass **81 tests with 1 skip**; the full suite
passes **203 tests with 1 skip**. No model, threshold, score, retrieval,
dashboard, or monitoring artifact changed. Details are in
[module4_trusted_model_loading_maintenance.md](docs/module4_trusted_model_loading_maintenance.md).

## Module 6 V1.2 — Dashboard authorization security maintenance (complete)

Added a separately versioned secure dashboard execution boundary in
[secure_app.py](src/dashboard/secure_app.py), using the Module 8 Stage 4
authorization facade before score retrieval, transaction details, review
submission, feedback summaries, and diagnostics. Missing or forged contexts
fail closed; no role selector or URL value is treated as authentication. Safe
field projections exclude labels, account identifiers, reviewer identities, and
notes. Historical Module 6 V1/V1.1 sources and manifests remain unchanged.
The maintenance manifest is
[module6_v1_2_security_maintenance_manifest.json](artifacts/module6_v1_2_security_maintenance_manifest.json),
with details in [module6_v1_2_security_maintenance.md](docs/module6_v1_2_security_maintenance.md).
The supported Streamlit [app.py](src/dashboard/app.py) launcher now delegates
to the secure entry point and denies unauthenticated launches. Its original V1.1
bytes were verified against the recorded hash before migration; the migrated
hash and command are recorded in the V1.2 manifest. Preserved historical source
snapshots remain outside the supported launcher. Real identity integration is
still deferred.

## Module 8 Stage 5 — Security regression, enforcement coverage, and dependency review (complete; freeze blocked)

Independently reviewed actual dashboard, ingestion, monitoring, feedback, and
model-loading entry points. Added [test_module8_stage5_security_regression.py](tests/test_module8_stage5_security_regression.py)
with nine synthetic coverage tests and recorded the enforcement matrix in
[module8_stage5_enforcement_coverage.md](docs/module8_stage5_enforcement_coverage.md).
The focused Stage 5 tests pass **9** tests; all Module 8, dashboard, ingestion,
risk-engine, and monitoring regressions pass **112 tests with 1 skip**; the full
suite passes **188 tests with 1 skip**. Frozen Module 4–7 checksums remain
unchanged and Module 7 reproducibility checks remain passed.

The review confirms that the legacy Streamlit entry point bypasses the Stage 4
authorization facade for score retrieval, details, feedback reads, and review
writes. Legacy risk-engine and development-evaluation paths also call
`joblib.load` without the Stage 3 wrapper. These high-priority bypasses are
documented and prevent a Module 8 freeze. A separately versioned security
maintenance release is required before those controls can be called enforced.
Dependency findings and the local inventory are documented in
[module8_stage5_dependency_review.md](docs/module8_stage5_dependency_review.md)
and [module8_stage5_security_regression.md](docs/module8_stage5_security_regression.md).

## Module 8 Stage 4 — Dashboard access controls and sensitive-data protection (complete)

Added the separate deny-by-default [dashboard_access.py](src/security/dashboard_access.py)
facade. It defines Viewer, Analyst, and Administrator prototype roles,
requires a trusted local context marker, enforces permissions before score/detail
reads, review writes, and feedback reads, and projects explicit analyst-safe
fields. Ground-truth labels, account identifiers, reviewer identities, notes,
and unverified outcomes are excluded from protected outputs. Frozen Module 6
and Module 7 code remains unchanged. The Stage 4 security tests pass **7**
tests. Real authentication, signed sessions, CSRF protection, and production
RBAC remain outside this research-prototype stage. Details are in
[module8_stage4_dashboard_security.md](docs/module8_stage4_dashboard_security.md).

## Module 8 Stage 2 — Input validation and secure data handling (2026-10-13)

- Added the additive security boundary in `src/security/input_validation.py`
  and its package exports. It validates required schemas, finite numeric values,
  supported PaySim categories, identifiers, control characters, paths, bounded
  CSV inspection, monitoring windows, and lifecycle configuration mappings with
  field-level errors that do not echo sensitive values.
- Integrated validation into the existing local ingestion adapter for CSV path,
  sample-row, and PaySim preparation inputs. Model feature definitions,
  scoring behavior, dashboard behavior, monitoring calculations, and frozen
  Modules 4–7 remain unchanged.
- Added `tests/test_module8_stage2_input_security.py` with **19** synthetic
  security regression tests. Focused security/adjacent tests pass **45 tests**;
  the complete project suite passes **160 tests**.
- Verified the recorded Module 4, Module 5, Module 6, and Module 7 freeze
  artifact SHA-256 values remain unchanged. No upload, network, authentication,
  Stage 3, retraining, MLflow, or deployment work was started.
- Detailed rules, limits, threat mapping, compatibility, and remaining risks
  are documented in `docs/module8_stage2_input_security.md`.

## Module 8 Stage 1 — Cybersecurity threat modeling and security testing architecture (2026-10-13)

- Verified the frozen Module 7 V1 monitoring baseline and reviewed the
  dashboard, monitoring, ingestion, risk-engine, model-adapter, metadata-sidecar,
  fraud-intelligence, and analyst-feedback interfaces.
- Added the planning-only threat model, security test plan, and staged
  implementation roadmap in `docs/module8_stage1_threat_model.md`,
  `docs/module8_stage1_security_test_plan.md`, and
  `docs/module8_implementation_plan.md`.
- The T01–T14 STRIDE-oriented register distinguishes demonstrated protections
  (schema/threshold validation, checksum validation, parameterized SQLite,
  analyst-safe projections, and monitoring privacy checks) from open risks that
  require later testing (authentication/authorization, path confinement,
  signed artifacts, safe deserialization, resource quotas, dependency
  provenance, tamper-evident reviews, and upload safety).
- No security controls were implemented. Frozen Modules 4–7 and their
  manifests were not modified. Module 8 Stages 2–6, retraining, MLflow, and
  Module 9 work were not started.

## Module 7 Stage 6 — V1 validation and freeze (2026-10-13)

- Independently validated the complete Module 7 monitoring system and froze it
  as `module7_v1_frozen`. The manifest is
  `artifacts/module7_v1_freeze_manifest.json`; the validation report is
  `docs/module7_v1_validation_and_freeze.md`.
- A new bounded run, `stage6_validation_step378_vs_379_20261013`, independently
  reproduced step 378 (**37,127 transactions, 5 alerts**) and step 379
  (**41,759 transactions, 26 alerts**). Independent KS, PSI, Jensen–Shannon,
  missingness, feedback, checksum, alignment, threshold, privacy, and
  reproducibility checks passed.
- Focused Module 7 validation passed **30 tests**; the full project suite passed
  **141 tests**. Module 4, Module 5, and Module 6 frozen artifacts retained
  their recorded SHA-256 checksums and were not modified.
- No ground-truth labels were used for monitoring decisions; analyst feedback
  remains mutable workflow data. No retraining, threshold change, MLflow, or
  Module 8 work was started.

## Module 7 Stage 5 — Monitoring lifecycle and reproducibility (2026-10-13)

- Recovery verification confirmed Modules 1–6, Module 7 Stages 1–4, and all
  frozen Module 4–6 artifacts are present. The pre-change full suite passed
  **135 tests**; Stage 5 was not present before this update.
- Added the versioned `src/monitoring/lifecycle.py` runner and
  `configs/module7_stage5_monitoring_v1.json`. It validates frozen model and
  threshold provenance, complete and ordered windows, source availability,
  run-ID uniqueness, privacy fields, and safe publication.
- The runner composes existing Stage 2, Stage 3, and Stage 4 functions, loads
  frozen inputs once, does not read raw PaySim CSV, and writes separate
  monitoring, drift, optional feedback, and manifest JSON artifacts. Failed
  runs record status and error details without replacing completed runs.
- Bounded validation compared steps 378 and 379: **37,127 / 41,759
  transactions** and **5 / 26 alerts**. The production-like feedback database
  was empty. Output checksums and privacy checks passed.
- Added `tests/test_monitoring_stage5.py`; focused validation passes **6 tests**
  and the complete project suite passes **141 tests**. The bounded artifact is
  `artifacts/module7_stage5_monitoring/stage5_step378_vs_379_v2/`; no Stage 6,
  MLflow, retraining, or Module 8 work is included.

## Recovery checkpoint — 2026-10-11

- Recovered checkpoint: Module 4 Stages 1–2 and Stage 3 preparation. The supplied
  conversation snapshot contains only the recovery request, not earlier implementation instructions.
- Existing model/metric files are present. No Module 4 development score cache or
  completed calibration/comparison artifact was found. Earlier metric values below
  are recorded results, not experiments rerun during recovery.
- Verified the pre-recovery baseline: `python -m pytest -q` passed all 27 tests.
- Resumed preparation by fixing direct calibration helper entry points to reject
  rows outside calibration steps (46–200 by default); custom fixture splits are explicit.
- Replaced repeated full-array threshold scans with sorted cumulative counts,
  preserving maximum-F1 selection, tied-score behavior, and lowest-threshold ties.
- Validation after recovery: **36 tests passed**; no editor diagnostics in the two
  changed Python files. Six new boundary cases failed before the fix and passed after it.
- Existing models, metrics, raw data, and the read-only conversation snapshot were
  not changed. No development experiment or final-holdout evaluation was run.
- Next checkpoint: finish the Stage 3 experiment runner and durable cache completion
  metadata, then perform the development-only comparison using calibration steps
  46–200 and evaluation steps 201–377. Keep steps 378–743 untouched until freeze.

## Module 4 Stage 3 development evaluation — 2026-10-11

- Completed the memory-bounded development pass using the frozen PaySim chronology.
  The new cache is `artifacts/module4_development_v1/score_cache.csv`; prior
  artifacts were preserved and the cache contains only steps 46–377.
- Calibration used 1,379,508 rows from steps 46–200. Development evaluation used
  3,024,694 rows from steps 201–377, including 1,949 frauds. Five configurations
  were predeclared; normalizers and alert thresholds were fitted on calibration
  rows only. Evaluation labels were used only for reporting metrics.
- Source scoring runtime was 2,215 seconds (36.9 minutes). The active Python
  process reached approximately 1,610 MB resident memory; this was CPU-bound but
  completed without a resource stop. The cache-based comparison rerun took 144 s.
- Results are saved in `artifacts/module4_development_v1/development_results_v3.json`.
  Random Forest alone was the strongest ranker (AP 0.5932, ROC-AUC 0.9940).
  Baseline anomaly reduced AP/ROC-AUC (0.4659/0.8561) but captured 498 vs 496
  frauds at the 500-alert budget. Behavioral anomaly and both anomalies reduced
  ranking quality further. Adding rules was weakest (AP 0.1051, ROC-AUC 0.6806).
- `final_holdout_accessed` is recorded as false. Steps 378–743 were not read.

## Module 4 Stage 4 final architecture — 2026-10-11

- Added `src/risk_engine/final_architecture.py` with version
  `module4_stage4_rf_primary_v1` and immutable model/threshold provenance.
- The frozen Random Forest probability is the only alert-driving score. The
  calibrated threshold is `0.3494391872980995`, with provenance explicitly tied
  to maximum-F1 calibration on steps 46–200. No anomaly or rule score modifies
  that probability or alert decision.
- Baseline and behavioral Isolation Forest outputs are labeled anomaly
  intensities (higher means more anomalous), never fraud probabilities. Rule
  identifiers, contextual rule score, alert, probability, independent anomaly
  indicators, and a human-readable explanation are returned in aligned rows.
- The interface reuses existing scoring adapters, complete-step behavioral state,
  and PaySim rules. It accepts target columns for offline checks but never reads
  them, and same-step state is committed only after transformation.
- Added five Stage 4 tests covering ranking consistency, threshold decisions,
  score alignment, target isolation, same-step leakage prevention, explanations,
  and reproducibility. Full validation passes 41 tests. No models were retrained,
  no caches were overwritten, and steps 378–743 were not accessed.

## Holdout recovery mechanism — 2026-10-11

- Added `src/risk_engine/holdout_recovery.py` and a new versioned recovery
  workflow. The original partial cache remains unchanged.
- Prefix verification checks raw source step counts/order, sequential row IDs,
  labels, finite scores, complete steps 378–428, frozen model SHA-256 hashes,
  feature definitions, architecture version, and threshold provenance.
- Recovery replays behavioral state through step 428 without rescoring the
  preserved prefix. Missing suffix steps are written as atomic files
  (`step_0429.csv`, etc.) with an atomic manifest update after each complete step.
  A later interruption therefore skips already-checkpointed scoring while still
  reconstructing the required state.
- Final combination has an integrity gate for exactly 955,744 rows, steps
  378–743, sequential aligned IDs, binary labels, and finite scores. Metrics are
  calculated only after that gate.
- Focused recovery and architecture validation passes **9 tests**. The full
  recovery run has not been launched; approval is still required before scoring
  steps 429–743.
- Actual read-only verification passed after normalizing SHA-256 case in the
  verifier: frozen architecture, threshold/provenance, model hashes, feature
  definitions, and all 597,486 prefix rows align with raw steps 378–428. No
  recovery directory or suffix checkpoint has been created yet.

The older gap/roadmap sections below are retained as historical planning notes;
this checkpoint and the completed-work entries take precedence where they conflict.

## Project scope

This repository is the current local implementation of the **AI-Driven Fraud Detection and Cybersecurity Framework — Architecture V2**. The present work covers offline PaySim ingestion, leakage-aware baseline modeling, and a versioned unsupervised behavioral anomaly-detection experiment. It is a research and engineering benchmark on simulated data, not a production deployment or evidence of operational effectiveness.

## Completed

### Module 1 — Data ingestion and preparation

- PaySim schema validation and bounded CSV inspection are implemented in `src/ingestion/adapters.py`.
- PaySim preparation validates binary labels, numeric transaction fields, and non-negative amounts.
- The preparation path excludes post-transaction balances and raw sender/receiver identifiers from the initial supervised feature set.
- A command-line inspection/preparation entry point exists in `src/ingestion/cli.py`.
- Ingestion tests cover valid input, missing columns, invalid labels, and inspection output.

### Module 2 — Supervised fraud baselines

- `train_paysim.py` implements chronological train/test modeling with Logistic Regression and Random Forest.
- `train_paysim_v2.py` implements chronological train/validation/test evaluation, validation-based threshold selection, and saved model artifacts.
- The one-million-row PaySim benchmark is preserved in `artifacts/paysim_v2/metrics_1m.json`.
- The latest recorded Random Forest test metrics are precision `0.56`, recall `0.5490`, F1 `0.5545`, and ROC-AUC `0.9851`.
- Existing serialized models and metrics under `artifacts/paysim` and `artifacts/paysim_v2` are preserved.

### Module 3 — Initial anomaly-detection baseline

- `src/anomaly_detection/train_isolation_forest.py` trains an unsupervised Isolation Forest.
- The current baseline reads a bounded PaySim sample, keeps whole simulation steps together, fits preprocessing on training data only, and evaluates on later steps.
- The baseline uses `amount`, `oldbalanceOrg`, `oldbalanceDest`, and `step`.
- The preserved 100,000-row result in `artifacts/anomaly_detection/metrics_100k_baseline.json` reports:
  - train/test rows: `72,726 / 27,274`
  - test fraud count: `7`
  - ROC-AUC: `0.5774`
  - average precision: `0.000366`
  - top-100 fraud detected: `0`
- The original model and metrics files under `artifacts/anomaly_detection` are not to be overwritten.

### Module 3 — Behavioral analytics increment

- `src/anomaly_detection/behavioral_features.py` computes prior sender/receiver history features in chronological `step` batches.
- Same-step transactions are transformed before any same-step state update, so they cannot see one another's activity.
- Features include prior sender count, prior three-step sender velocity, historical sender mean amount, amount-to-history ratio, sender transaction-type history, prior receiver count, and receiver amount history.
- `tests/test_behavioral_features.py` verifies same-step isolation, chronological updates, row-order independence within a step, and schema validation.
- `src/anomaly_detection/train_isolation_forest_behavioral.py` compares the original feature set and behavioral feature set on the exact original 100k-row split.
- New artifacts are stored under `artifacts/anomaly_detection_behavioral`.
- The matched baseline reproduced the preserved baseline exactly: ROC-AUC `0.5774`, average precision `0.000366`, and zero fraud captured at top 10/50/100/500.
- The first behavioral model scored ROC-AUC `0.5105`, average precision `0.000280`, and also captured zero fraud at top 10/50/100/500. This is a negative result on the 100k slice, not evidence that behavioral features are ineffective in general.
- The 1M-row matched experiment is saved under `artifacts/anomaly_detection_behavioral_1m` and uses the same fixed Isolation Forest configuration for both models; no final-test tuning was performed.
- On 1M rows, the chronological split contains 699,825 training rows through step 36 and 300,175 test rows from step 37 onward, with 118 test fraud rows.
- PaySim account activity is highly asymmetric: only 241 of 999,759 origin accounts repeat, while 76,035 of 422,896 destination accounts repeat. Repeated origins account for `0.0482%` of rows; repeated destinations account for `65.3139%` of rows.
- Only 114 test rows (`0.0380%`) have a sender seen in training, while 154,110 test rows (`51.3401%`) have a receiver seen in training. Sender-history features are therefore almost always zero; receiver-history features are nonzero for approximately `58.5%` of test rows.
- The 1M baseline scored ROC-AUC `0.6739`, average precision `0.003064`, and captured `0/0/0/2` frauds at top `10/50/100/500`.
- The 1M behavioral model scored ROC-AUC `0.6362`, average precision `0.012157`, and captured `1/2/3/6` frauds at top `10/50/100/500`. It improved average precision and alert-budget recall, but not ROC-AUC; this is a ranking trade-off, not universal model improvement.

### Tests and documentation

- Automated tests exist for the generic supervised pipeline and ingestion adapter.
- Project guidance, Module 1 guidance, next steps, and a development log are present.
- The project contains the raw PaySim CSV, a 100k processed sample, and saved model artifacts.

### Module 4 — Integrated risk assessment, Stages 1–2

- The earlier 140,713-row count for steps 42–45 came from the first 1,000,000 CSV rows and ended partway through step 45. The full file contains 143,387 rows across complete steps 42–45, including 2,674 additional step-45 rows.
- The full chronology contains steps 1–743 and 6,362,620 transactions. The approved Module 4 development period is steps 46–377; the untouched final holdout is steps 378–743. Steps 42–45 remain diagnostic-only.
- `src/risk_engine/contracts.py` validates transaction-time PaySim inputs.
- `src/risk_engine/behavioral_state.py` provides stateful complete-step processing and chunked CSV iteration while preserving the Module 3 feature definitions.
- `src/risk_engine/scorers.py` adapts the frozen supervised and anomaly model artifacts.
- `src/risk_engine/rules.py`, `normalization.py`, `fusion.py`, and `decisions.py` implement transparent rules, development-fitted normalization primitives, configurable fusion, risk tiers, alerts, and explanation provenance.
- `tests/test_risk_engine.py` covers contracts, streaming/batch equivalence, same-step isolation, deterministic bounded scores, missing inputs, and explanation provenance.
- Stages 1–2 validation passes with 22 tests. No Module 4 fusion parameters have been fitted, and no development or final-holdout evaluation has been run.
- Stage 3 preparation is implemented in `src/risk_engine/development_pipeline.py`. It scores and stores the four
  aligned components once for steps 46–377, while preserving step-batched behavioral history through step 45.
- The fixed development split is calibration steps 46–200 and development evaluation steps 201–377. This is a
  predetermined chronological split, not a performance-selected boundary. Steps 378–743 remain untouched.
- The focused pipeline tests pass. They cover chunk-boundary correctness, aligned cache rows, reproducibility across
  chunk sizes, calibration rejection of evaluation rows, frozen normalization application, and explanation fallback.
- Fusion weights are selected, when requested, from a fixed candidate set using calibration labels only; no
  development-evaluation or final-holdout labels are used for weight selection.
- Profiling steps 1–55 processed 1,030,311 rows in 85.4 seconds; behavioral processing took 82.5 seconds and CSV
  parsing/boundary handling approximately 3.2 seconds. The main memory risk is the account-history dictionaries,
  which reached approximately 1.03 million sender and sender/type entries by step 55; the three-step velocity state
  remained small. No full Stage 3 model-comparison experiment has been run.

## Current limitations and items needing improvement

### Module 3 feature gap

The new anomaly experiment now uses behavioral history, but its feature set and evaluation need further improvement. It does not yet represent:

- historical sender transaction frequency;
- transaction velocity over prior hours or steps;
- historical average transaction amount;
- amount deviation from an account’s prior behavior;
- unusual sender/receiver or transaction-type patterns.

The raw PaySim identifiers are available in the source CSV but are intentionally not used by the baseline. A new feature-engineering path must use them only to derive history-based aggregates and must not expose raw identifiers as model predictors.

### Leakage and time semantics

- PaySim provides hourly `step` values but does not establish an ordering within an hour. Same-step transactions must therefore be treated as simultaneous for historical features.
- A transaction’s behavioral features must be computed from strictly earlier steps. Current-step transactions must not contribute to their own history or to another transaction’s history within the same step.
- Aggregates must be fit or updated in chronological order and evaluated only on information available before each test step.
- The existing anomaly baseline and the supervised benchmarks use different sample sizes and split definitions, so direct metric comparisons require a deliberately matched experiment.

### Evaluation limitations

- The anomaly baseline test set contains only seven fraud examples, making ranking metrics unstable.
- The current anomaly script reports ROC-AUC, average precision, and a top-100 review result, but not a broader alert-budget curve or multiple fixed alert volumes.
- There is no validation split for selecting Isolation Forest hyperparameters or feature configurations.
- No paired comparison currently exists between the original and behavioral-feature models on the exact same rows and test steps.
- PaySim is simulated; results must remain explicitly limited to this benchmark.

### Engineering limitations

- The anomaly script is a standalone experiment rather than a reusable feature-engineering module with unit tests.
- The README architecture summary still says anomaly detection is not implemented, although the Module 3 script and artifacts now exist; documentation should be synchronized after the new experiment is established.
- The repository is not currently a local Git repository, so file history and change provenance cannot be inferred from Git metadata.
- The project has no evaluated integrated risk-scoring deployment, explanation/RAG layer, dashboard, monitoring loop, feedback store, or cybersecurity test harness yet.
- Module 4 infrastructure and calibration utilities now exist, but no development calibration/model-comparison run
  or final-holdout evaluation has been completed.

## Proposed remaining roadmap

1. **Behavioral feature refinement:** focus on receiver-side history because sender identities are almost entirely one-shot in this PaySim slice. Use a chronological validation period for any feature or model configuration selection.
2. **Matched anomaly evaluation:** retain the completed 1M comparison as the current Module 3 reference and use future experiments only when they preserve identical rows, boundaries, and alert budgets.
3. **Evaluation expansion:** retain average precision, ROC-AUC, precision/recall at fixed alert counts, fraud captured in top 10/50/100/500 alerts, and split/provenance metadata. Use validation data for configuration choices.
4. **Memory and reproducibility checks:** continue using compact dtypes, bounded columns, and step-wise processing appropriate for a 16 GB machine; record parameters and feature definitions in metrics JSON.
5. **Documentation synchronization:** keep the README, Module 3 documentation, and development log aligned with actual experiment dates and negative as well as positive results.
6. **Later modules:** build the integrated risk engine, grounded fraud-intelligence explanations, investigation dashboard, monitoring/retraining workflow, and cybersecurity/security-control tests only after the anomaly evaluation contract is stable.

## Recommended immediate implementation sequence

Before modifying existing scripts, create new versioned components in this order:

1. `src/anomaly_detection/behavioral_features.py` with pure, testable state-update logic.
2. Unit tests for chronological behavior and leakage prevention.
3. A new experiment runner, leaving `train_isolation_forest.py` and its artifacts unchanged.
4. A matched baseline-versus-behavioral report under a new artifact directory.
5. Documentation updates after the experiment and tests pass.

This sequence preserves the current baseline while making the next results reproducible and directly comparable.
## Module 4 final holdout recovery

The checkpointed recovery completed steps 429–743 using the frozen Stage 4 architecture and the immutable prefix from steps 378–428. The complete artifact and report are in `artifacts/module4_final_holdout_recovery_v1/`.

- 955,744 transactions; 4,010 frauds
- Average precision 0.747744; ROC-AUC 0.992739
- Frozen-threshold precision 0.908425; recall 0.556608; F1 0.690274
- Confusion matrix: TP 2,232; FP 225; FN 1,778; TN 951,509
- Runtime 5,575.22 seconds; observed RSS approximately 1.95 GB during reconstruction
- Integrity checks passed for source alignment, complete steps 378–743, unique row IDs, labels, finite scores, and duplicate/missing transaction checks

## Module 5 Version 1 freeze

Module 5 Version 1 is frozen as the research prototype architecture `module5_v1_frozen`. The freeze manifest is [module5_v1_freeze_manifest.json](../artifacts/module5_authoritative_v1/module5_v1_freeze_manifest.json).

- Contracts, ingestion, provenance validation, deterministic TF-IDF retrieval, query normalization, grounded explanations, safety checks, and read-only Module 4 integration are included.
- The authoritative knowledge base is `module5_authoritative_v1` with 10 curated government-source summaries and 10 indexed chunks.
- Stage 6D revised retrieval metrics are recorded in [stage6d_retrieval_comparison.json](../artifacts/module5_authoritative_v1/stage6d_retrieval_comparison.json).
- The full test suite passed 89 tests.
- Module 4 models, thresholds, scores, caches, and evaluation artifacts remain unchanged.

Known limitations remain: retrieval is lexical and sensitive to wording; some multi-pattern cases miss one of several expected documents in the top three; evaluation fixtures are small diagnostic sets; and authoritative entries are independently authored summaries rather than original government-document text or verbatim quotations. PaySim is simulated and the prototype has no production deployment evidence.

## Module 6 Stage 6 validation and V1 freeze preparation

The complete local dashboard workflow was validated: frozen score loading, overview and explorer filtering, sidecar metadata alignment, Module 5 authoritative retrieval and grounded explanations, and append-only analyst review persistence. The validation report is [module6_stage6_validation.md](docs/module6_stage6_validation.md). Module 6 V1 is formally frozen as `module6_dashboard_v1_frozen`; the final manifest is [module6_v1_freeze_manifest.json](artifacts/module6_v1_freeze_manifest.json). Mutable analyst feedback remains outside the immutable boundary. Module 4 and Module 5 results are historical frozen research outputs over simulated PaySim data; future monitoring, retraining, and operational cybersecurity work belongs to Modules 7 and 8.
## Module 7 Stage 1 — monitoring architecture and data contracts

Stage 1 architecture and contract design has begun. The proposed read-only monitoring architecture, contracts, staged implementation plan, and Module 6 post-freeze issue register are documented in [module7_stage1_architecture.md](docs/module7_stage1_architecture.md), [module7_stage1_data_contracts.md](docs/module7_stage1_data_contracts.md), [module7_implementation_plan.md](docs/module7_implementation_plan.md), and [module6_post_freeze_issue_register.md](docs/module6_post_freeze_issue_register.md). No monitoring pipeline, drift calculation, retraining workflow, or Module 6 correction was implemented.

## Module 6 V1.1 maintenance correction

The verified Transaction Explorer label-disclosure defect was corrected in the separately versioned V1.1 working-tree maintenance update. Analyst-facing score tables now use an explicit safe-field allowlist; internal `isFraud` alignment labels and account identifiers remain backend-only. The historical V1 freeze manifest is unchanged, and the V1 source snapshot plus maintenance manifest are recorded under `artifacts/module6_v1_1/`. Module 6 V1.1 regression tests passed.
### Module 7 Stage 2 — Monitoring (complete)

Implemented a separate read-only `src/monitoring` package for deterministic transaction, alert, fraud-probability, anomaly-intensity, metadata, missingness, and complete-step window summaries. Outputs are label-free versioned JSON with source checksums and atomic publication. Complete-step validation for frozen step 378 passed with authoritative count matching; focused synthetic tests and the complete suite (119 tests) passed. Drift detection, feedback analytics, retraining, and dashboard work remain future stages.

### Module 7 Stage 3 — Drift detection (complete)

Added read-only ordered-window data and prediction drift comparisons in `src/monitoring/drift.py`. Fixed-bin PSI, empirical KS, Jensen–Shannon categorical divergence, missingness changes, frozen alert-rate comparisons, and probability quantiles are reported with provenance and limitations. Complete-step counts, metadata alignment, duplicate detection, and reference-before-comparison rules are enforced. Bounded steps 378–379 validation passed; no frozen artifact or threshold was changed. Feedback analytics, MLflow, retraining, and dashboard work remain future stages.

### Module 7 Stage 4 — Analyst feedback analysis (complete)

Added read-only SQLite feedback analysis in `src/monitoring/feedback.py`. The production-like feedback database is the default source; the demonstration database is excluded. Event and transaction counts, statuses, repeat activity, UTC dates/windows, latest-status summaries, and optional frozen-score alignment are reported without reviewer labels, notes, ground-truth labels, or model changes. The clean database currently has zero events; synthetic tests cover the nonempty path and read-only integrity. MLflow, controlled retraining, and dashboard extensions remain future work.
### Module 8 Stage 3 — SQLite, filesystem, and artifact security (complete)

Added the non-invasive security boundary [storage_security.py](src/security/storage_security.py)
for local feedback databases, trusted filesystem paths, no-clobber JSON
publication, and pre-load SHA-256 verification of serialized artifacts. SQLite
reads are read-only, feedback fields are validated, demonstration and
production-like databases can be isolated, and errors are sanitized. Existing
frozen Modules 4–7 code and artifacts were not modified. Stage 3 regression
tests passed 12 tests (one host-dependent symlink test skipped); the focused
Stage 3/adjacent set passed 57 tests with one skip, and the full suite passed
172 tests with one skip. Frozen artifact checksums remain unchanged. Direct
legacy joblib loaders remain a documented integration gap for the later access
control stage; callers requiring secure deserialization must use the wrapper.
Details and reproduction steps are in [module8_stage3_storage_security.md](docs/module8_stage3_storage_security.md).
