# Implementation Status

This report describes the current implementation state of the Fraud Detection
and Cybersecurity Framework V2. It records completed modules, validation
evidence, frozen research artifacts, known limitations, and work that remains
outside the completed scope. The framework is a local research prototype based
on simulated PaySim data, not a production deployment or evidence of
operational effectiveness.

## Current release status

### Module 8 Stage 6 — Final security validation and V1 freeze (complete)

The supported ingestion boundary, secure dashboard launcher, authorization
facade, SQLite and filesystem boundaries, trusted model loaders, and monitoring
integrity controls have been independently validated. The Stage 6 matrix passed
**113 tests with 1 skip**, and the full suite passed **211 tests with 1 skip**.
Modules 4–7 frozen artifacts and historical manifests retain their recorded
SHA-256 values. No model retraining, rescoring, threshold change, or monitoring
rewrite occurred.

Module 8 is frozen as the research-prototype release
`module8_v1_frozen`. Final validation includes explicit severity-classified
limitations. This is not production security certification; authentication,
signed sessions, managed RBAC, authenticated artifact provenance, dependency
locking, and symlink-capable CI remain deployment requirements.

### Module 4 trusted model-loading security maintenance (complete)

Trusted model loading uses source-controlled role, path, and SHA-256 anchors
that match the frozen Module 4 recovery manifest. Exact frozen artifacts are
verified before deserialization. Original source hashes and trusted model
checksums remain recorded in the maintenance manifest. Focused risk and security
regressions pass **81 tests with 1 skip**; the full suite passes **203 tests
with 1 skip**. No model, threshold, score, retrieval, dashboard, or monitoring
artifact changed.

### Module 6 V1.2 — Dashboard authorization security maintenance (complete)

The separately versioned secure dashboard execution boundary uses the Module 8
Stage 4 authorization facade before score retrieval, transaction details, review
submission, feedback summaries, and diagnostics. Missing or forged contexts fail
closed, and neither a role selector nor a URL value is treated as authentication.
Safe field projections exclude labels, account identifiers, reviewer identities,
and notes. Historical Module 6 V1/V1.1 sources and manifests remain unchanged.

The supported Streamlit launcher delegates to the secure entry point and denies
unauthenticated launches. Its original V1.1 bytes were verified against the
recorded hash before migration; the migrated hash and command remain recorded in
the V1.2 manifest. Preserved historical source snapshots remain outside the
supported launcher. Real identity integration is still deferred.

### Module 8 Stage 5 — Security regression, enforcement coverage, and dependency review (complete; freeze blocked)

Actual dashboard, ingestion, monitoring, feedback, and model-loading entry
points were independently reviewed. Nine synthetic coverage tests exercise the
Stage 5 security regression surface. The focused Stage 5 tests pass **9**
tests; all Module 8, dashboard, ingestion, risk-engine, and monitoring
regressions pass **112 tests with 1 skip**; the full suite passes **188 tests
with 1 skip**. Frozen Module 4–7 checksums remain unchanged, and Module 7
reproducibility checks remain passed.

The review confirms that the legacy Streamlit entry point bypasses the Stage 4
authorization facade for score retrieval, details, feedback reads, and review
writes. Legacy risk-engine and development-evaluation paths also call
`joblib.load` without the Stage 3 wrapper. These high-priority bypasses prevent a
Module 8 freeze. A separately versioned security maintenance release is required
before those controls can be called enforced. Dependency findings and the local
inventory are recorded in the security review materials.

### Module 8 Stage 4 — Dashboard access controls and sensitive-data protection (complete)

The separate deny-by-default dashboard access facade defines Viewer, Analyst,
and Administrator prototype roles. It requires a trusted local context marker,
enforces permissions before score and detail reads, review writes, and feedback
reads, and projects explicit analyst-safe fields. Ground-truth labels, account
identifiers, reviewer identities, notes, and unverified outcomes are excluded
from protected outputs. Frozen Module 6 and Module 7 code remains unchanged.
The Stage 4 security tests pass **7** tests. Real authentication, signed
sessions, CSRF protection, and production RBAC remain outside this
research-prototype stage.

### Module 8 Stage 3 — SQLite, filesystem, and artifact security (complete)

The non-invasive security boundary protects local feedback databases, trusted
filesystem paths, no-clobber JSON publication, and serialized artifacts through
pre-load SHA-256 verification. SQLite reads are read-only, feedback fields are
validated, demonstration and production-like databases can be isolated, and
errors are sanitized. Existing frozen Modules 4–7 code and artifacts were not
modified. Stage 3 regression tests passed **12 tests**, with one host-dependent
symlink test skipped. The focused Stage 3 and adjacent set passed **57 tests
with one skip**, and the full suite passed **172 tests with one skip**. Frozen
artifact checksums remain unchanged.

Direct legacy `joblib` loaders remain a documented integration gap for the
later access-control stage; callers requiring secure deserialization must use the
security wrapper.

### Module 8 Stage 2 — Input validation and secure data handling (2026-10-13)

- The additive security boundary validates required schemas, finite numeric
  values, supported PaySim categories, identifiers, control characters, paths,
  bounded CSV inspection, monitoring windows, and lifecycle configuration
  mappings. Field-level errors do not echo sensitive values.
- Existing local ingestion accepts validated CSV paths, sample-row inputs, and
  PaySim preparation inputs. Model feature definitions, scoring behavior,
  dashboard behavior, monitoring calculations, and frozen Modules 4–7 remain
  unchanged.
- Synthetic security regression coverage contains **19 tests**. Focused
  security and adjacent tests pass **45 tests**; the complete project suite
  passes **160 tests**.
- Recorded Module 4, Module 5, Module 6, and Module 7 freeze-artifact SHA-256
  values remain unchanged. No upload, network, authentication, Stage 3,
  retraining, MLflow, or deployment work was started.

### Module 8 Stage 1 — Cybersecurity threat modeling and security testing architecture (2026-10-13)

- The frozen Module 7 V1 monitoring baseline and the dashboard, monitoring,
  ingestion, risk-engine, model-adapter, metadata-sidecar, fraud-intelligence,
  and analyst-feedback interfaces were reviewed.
- The planning-only threat model, security test plan, and staged implementation
  roadmap are in place.
- The T01–T14 STRIDE-oriented register distinguishes demonstrated protections
  (schema and threshold validation, checksum validation, parameterized SQLite,
  analyst-safe projections, and monitoring privacy checks) from open risks that
  require later testing. Open risks include authentication and authorization,
  path confinement, signed artifacts, safe deserialization, resource quotas,
  dependency provenance, tamper-evident reviews, and upload safety.
- No security controls were implemented at this stage. Frozen Modules 4–7 and
  their manifests were not modified. Module 8 Stages 2–6, retraining, MLflow,
  and Module 9 work were not started.

## Module 7 status

### Module 7 Stage 6 — V1 validation and freeze (2026-10-13)

The complete Module 7 monitoring system was independently validated and frozen
as `module7_v1_frozen`. A bounded run independently reproduced step 378
(**37,127 transactions, 5 alerts**) and step 379 (**41,759 transactions,
26 alerts**). Independent KS, PSI, Jensen–Shannon, missingness, feedback,
checksum, alignment, threshold, privacy, and reproducibility checks passed.

Focused Module 7 validation passed **30 tests**; the full project suite passed
**141 tests**. Module 4, Module 5, and Module 6 frozen artifacts retained their
recorded SHA-256 checksums and were not modified. No ground-truth labels were
used for monitoring decisions; analyst feedback remains mutable workflow data.
No retraining, threshold change, MLflow, or Module 8 work was started.

### Module 7 Stage 5 — Monitoring lifecycle and reproducibility (2026-10-13)

Recovery verification confirmed Modules 1–6, Module 7 Stages 1–4, and all
frozen Module 4–6 artifacts. The pre-change full suite passed **135 tests**;
Stage 5 was not present before this work.

The versioned monitoring lifecycle runner validates frozen model and threshold
provenance, complete and ordered windows, source availability, run-ID
uniqueness, privacy fields, and safe publication. It composes existing Stage 2,
Stage 3, and Stage 4 functions, loads frozen inputs once, does not read raw
PaySim CSV, and writes separate monitoring, drift, optional feedback, and
manifest JSON artifacts. Failed runs record status and error details without
replacing completed runs.

Bounded validation compared steps 378 and 379: **37,127 / 41,759
transactions** and **5 / 26 alerts**. The production-like feedback database was
empty. Output checksums and privacy checks passed. Focused validation passes
**6 tests**, and the complete project suite passes **141 tests**. The bounded
artifact contains the step-378-versus-379 monitoring run; no Stage 6, MLflow,
retraining, or Module 8 work is included.

### Module 7 Stage 4 — Analyst feedback analysis (complete)

Read-only SQLite feedback analysis reports event and transaction counts,
statuses, repeat activity, UTC dates and windows, latest-status summaries, and
optional frozen-score alignment without reviewer labels, notes, ground-truth
labels, or model changes. The production-like feedback database is the default
source and the demonstration database is excluded. The clean database currently
has zero events; synthetic tests cover the nonempty path and read-only
integrity. MLflow, controlled retraining, and dashboard extensions remain future
work.

### Module 7 Stage 3 — Drift detection (complete)

Read-only ordered-window data and prediction drift comparisons report fixed-bin
PSI, empirical KS, Jensen–Shannon categorical divergence, missingness changes,
frozen alert-rate comparisons, and probability quantiles with provenance and
limitations. Complete-step counts, metadata alignment, duplicate detection, and
reference-before-comparison rules are enforced. Bounded steps 378–379
validation passed; no frozen artifact or threshold changed. Feedback analytics,
MLflow, retraining, and dashboard work remain future stages.

### Module 7 Stage 2 — Monitoring (complete)

A separate read-only monitoring package provides deterministic transaction,
alert, fraud-probability, anomaly-intensity, metadata, missingness, and
complete-step window summaries. Outputs are label-free, versioned JSON with
source checksums and atomic publication. Complete-step validation for frozen
step 378 passed with authoritative count matching; focused synthetic tests and
the complete suite (**119 tests**) passed. Drift detection, feedback analytics,
retraining, and dashboard work remain future stages.

### Module 7 Stage 1 — Monitoring architecture and data contracts

Stage 1 architecture and contract design has begun. The proposed read-only
monitoring architecture, contracts, staged implementation plan, and Module 6
post-freeze issue register are documented as planning materials. No monitoring
pipeline, drift calculation, retraining workflow, or Module 6 correction was
implemented at this stage.

## Module 6 status

### Module 6 Stage 6 — Validation and V1 freeze preparation

The complete local dashboard workflow was validated: frozen score loading,
overview and explorer filtering, sidecar metadata alignment, Module 5
authoritative retrieval and grounded explanations, and append-only analyst
review persistence. Module 6 V1 is formally frozen as
`module6_dashboard_v1_frozen`; mutable analyst feedback remains outside the
immutable boundary. Module 4 and Module 5 results are historical frozen
research outputs over simulated PaySim data. Future monitoring, retraining, and
operational cybersecurity work belongs to Modules 7 and 8.

### Module 6 V1.1 maintenance correction

The verified Transaction Explorer label-disclosure defect was corrected in the
separately versioned V1.1 working-tree maintenance update. Analyst-facing score
tables now use an explicit safe-field allowlist; internal `isFraud` alignment
labels and account identifiers remain backend-only. The historical V1 freeze
manifest is unchanged, and the V1 source snapshot plus maintenance manifest
remain recorded under the V1.1 artifact set. Module 6 V1.1 regression tests
passed.

### Module 6 V1.2 maintenance status

The V1.2 secure launcher and authorization boundary are complete as described in
the current release status. Real identity integration remains deferred, and the
historical V1/V1.1 sources and manifests remain unchanged.

## Module 5 status

### Module 5 Version 1 freeze

Module 5 Version 1 is frozen as the research-prototype architecture
`module5_v1_frozen`. Contracts, ingestion, provenance validation, deterministic
TF-IDF retrieval, query normalization, grounded explanations, safety checks, and
read-only Module 4 integration are included.

The authoritative knowledge base is `module5_authoritative_v1` with 10 curated
government-source summaries and 10 indexed chunks. Stage 6D revised retrieval
metrics are recorded in the frozen comparison artifact. The full test suite
passed **89 tests**. Module 4 models, thresholds, scores, caches, and evaluation
artifacts remain unchanged.

Known limitations remain: retrieval is lexical and sensitive to wording; some
multi-pattern cases miss one of several expected documents in the top three;
evaluation fixtures are small diagnostic sets; and authoritative entries are
independently authored summaries rather than original government-document text
or verbatim quotations. PaySim is simulated, and the prototype has no
production deployment evidence.

## Module 4 status

### Recovery checkpoint — 2026-10-11

The recovered checkpoint covers Module 4 Stages 1–2 and Stage 3 preparation.
The supplied conversation snapshot contains only the recovery request, not
earlier implementation instructions.

Existing model and metric files are present. No Module 4 development score
cache or completed calibration/comparison artifact was found. Earlier metric
values below are recorded results, not experiments rerun during recovery.

The pre-recovery baseline passed all **27 tests**. Direct calibration helper
entry points now reject rows outside calibration steps 46–200 by default, while
custom fixture splits are explicit. Repeated full-array threshold scans were
replaced with sorted cumulative counts, preserving maximum-F1 selection,
tied-score behavior, and lowest-threshold ties.

Validation after recovery: **36 tests passed**; no editor diagnostics appeared
in the two changed Python files. Six new boundary cases failed before the fix and
passed afterward. Existing models, metrics, raw data, and the read-only
conversation snapshot were not changed. No development experiment or final
holdout evaluation was run.

The next checkpoint is the Stage 3 experiment runner and durable cache
completion metadata, followed by the development-only comparison using
calibration steps 46–200 and evaluation steps 201–377. Steps 378–743 remain
untouched until freeze.

### Module 4 Stage 1 — Data contracts and stateful processing

The transaction-time PaySim contract validates model inputs. Stateful complete-
step processing and chunked CSV iteration preserve the Module 3 feature
definitions. The scoring adapters support the frozen supervised and anomaly
model artifacts. Transparent rules, development-fitted normalization
primitives, configurable fusion, risk tiers, alerts, and explanation provenance
are available for the integrated risk engine.

Stages 1–2 validation passes with **22 tests**. No Module 4 fusion parameters
have been fitted, and no development or final-holdout evaluation has been run at
this checkpoint.

Stage 3 preparation scores and stores the four aligned components once for
steps 46–377 while preserving step-batched behavioral history through step 45.
The fixed development split is calibration steps 46–200 and development
evaluation steps 201–377. This is a predetermined chronological split, not a
performance-selected boundary; steps 378–743 remain untouched. Focused pipeline
tests cover chunk-boundary correctness, aligned cache rows, reproducibility
across chunk sizes, calibration rejection of evaluation rows, frozen
normalization application, and explanation fallback. When requested, fusion
weights are selected from a fixed candidate set using calibration labels only;
development-evaluation and final-holdout labels are not used for weight
selection.

Profiling steps 1–55 processed 1,030,311 rows in 85.4 seconds. Behavioral
processing took 82.5 seconds and CSV parsing and boundary handling took
approximately 3.2 seconds. The main memory risk is the account-history
dictionaries, which reached approximately 1.03 million sender and sender/type
entries by step 55; the three-step velocity state remained small. No full Stage
3 model-comparison experiment had been run at that checkpoint.

### Module 4 Stage 3 — Development evaluation (2026-10-11)

The memory-bounded development pass uses the frozen PaySim chronology. The score
cache contains only steps 46–377, while prior artifacts were preserved.

Calibration used 1,379,508 rows from steps 46–200. Development evaluation used
3,024,694 rows from steps 201–377, including 1,949 frauds. Five configurations
were predeclared; normalizers and alert thresholds were fitted on calibration
rows only. Evaluation labels were used only for reporting metrics.

Source scoring runtime was 2,215 seconds (36.9 minutes). The active Python
process reached approximately 1,610 MB resident memory; the run was CPU-bound
but completed without a resource stop. The cache-based comparison rerun took
144 seconds.

Random Forest alone was the strongest ranker (AP 0.5932, ROC-AUC 0.9940).
Baseline anomaly reduced AP/ROC-AUC (0.4659/0.8561) but captured 498 versus 496
frauds at the 500-alert budget. Behavioral anomaly and both-anomaly
configurations reduced ranking quality further. Adding rules was weakest
(AP 0.1051, ROC-AUC 0.6806).

`final_holdout_accessed` is recorded as false. Steps 378–743 were not read.

### Module 4 Stage 4 — Final architecture (2026-10-11)

The final architecture is versioned as `module4_stage4_rf_primary_v1` with
immutable model and threshold provenance. The frozen Random Forest probability
is the only alert-driving score. The calibrated threshold is
`0.3494391872980995`, with provenance explicitly tied to maximum-F1 calibration
on steps 46–200. No anomaly or rule score modifies that probability or alert
decision.

Baseline and behavioral Isolation Forest outputs are anomaly intensities
(higher means more anomalous), never fraud probabilities. Rule identifiers,
contextual rule score, alert, probability, independent anomaly indicators, and
a human-readable explanation are returned in aligned rows.

The interface reuses existing scoring adapters, complete-step behavioral state,
and PaySim rules. It accepts target columns for offline checks but never reads
them, and same-step state is committed only after transformation. Five Stage 4
tests cover ranking consistency, threshold decisions, score alignment, target
isolation, same-step leakage prevention, explanations, and reproducibility.
Full validation passes **41 tests**. No models were retrained, no caches were
overwritten, and steps 378–743 were not accessed.

### Holdout recovery mechanism — 2026-10-11

The versioned recovery workflow preserves the original partial cache and
supports checkpointed completion. Prefix verification checks raw source step
counts and order, sequential row IDs, labels, finite scores, complete steps
378–428, frozen model SHA-256 hashes, feature definitions, architecture version,
and threshold provenance.

Recovery replays behavioral state through step 428 without rescoring the
preserved prefix. Missing suffix steps are written as atomic files, with an
atomic manifest update after each complete step. A later interruption can skip
already checkpointed scoring while still reconstructing the required state.

Final combination has an integrity gate for exactly 955,744 rows, steps
378–743, sequential aligned IDs, binary labels, and finite scores. Metrics are
calculated only after that gate. Focused recovery and architecture validation
passes **9 tests**. The full recovery run has not been launched; approval is
still required before scoring steps 429–743.

Read-only verification passed after normalizing SHA-256 case in the verifier:
frozen architecture, threshold and provenance, model hashes, feature
definitions, and all 597,486 prefix rows align with raw steps 378–428. No
recovery directory or suffix checkpoint has been created yet.

### Module 4 final holdout recovery

The checkpointed recovery completed steps 429–743 using the frozen Stage 4
architecture and immutable prefix from steps 378–428. The complete artifact and
report are in the final holdout recovery artifact set.

- 955,744 transactions; 4,010 frauds
- Average precision 0.747744; ROC-AUC 0.992739
- Frozen-threshold precision 0.908425; recall 0.556608; F1 0.690274
- Confusion matrix: TP 2,232; FP 225; FN 1,778; TN 951,509
- Runtime 5,575.22 seconds; observed RSS approximately 1.95 GB during
  reconstruction
- Integrity checks passed for source alignment, complete steps 378–743, unique
  row IDs, labels, finite scores, and duplicate or missing transaction checks

## Earlier module implementation baseline

The following baseline records the initial architecture and benchmark status.
Later completed-work entries above take precedence where they conflict with
these earlier planning notes.

### Module 1 — Data ingestion and preparation (complete)

- PaySim schema validation and bounded CSV inspection are implemented.
- PaySim preparation validates binary labels, numeric transaction fields, and
  non-negative amounts.
- The preparation path excludes post-transaction balances and raw
  sender/receiver identifiers from the initial supervised feature set.
- A command-line inspection and preparation entry point exists.
- Ingestion tests cover valid input, missing columns, invalid labels, and
  inspection output.

### Module 2 — Supervised fraud baselines (complete)

- Chronological train/test modeling is available for Logistic Regression and
  Random Forest.
- Chronological train/validation/test evaluation, validation-based threshold
  selection, and saved model artifacts are available.
- The one-million-row PaySim benchmark is preserved in the Module 2 artifact
  set.
- The latest recorded Random Forest test metrics are precision `0.56`, recall
  `0.5490`, F1 `0.5545`, and ROC-AUC `0.9851`.
- Existing serialized models and metrics under the PaySim artifact sets are
  preserved.

### Module 3 — Initial anomaly-detection baseline (complete)

- An unsupervised Isolation Forest trains on a bounded PaySim sample, keeps
  whole simulation steps together, fits preprocessing on training data only,
  and evaluates on later steps.
- The baseline uses `amount`, `oldbalanceOrg`, `oldbalanceDest`, and `step`.
- The preserved 100,000-row result reports:
  - train/test rows: `72,726 / 27,274`
  - test fraud count: `7`
  - ROC-AUC: `0.5774`
  - average precision: `0.000366`
  - top-100 fraud detected: `0`
- The original model and metrics artifacts are not to be overwritten.

### Module 3 — Behavioral analytics increment (complete)

- Behavioral features compute prior sender and receiver history in chronological
  `step` batches.
- Same-step transactions are transformed before same-step state updates, so
  they cannot see one another's activity.
- Features include prior sender count, prior three-step sender velocity,
  historical sender mean amount, amount-to-history ratio, sender
  transaction-type history, prior receiver count, and receiver amount history.
- Tests verify same-step isolation, chronological updates, row-order
  independence within a step, and schema validation.
- The original and behavioral feature sets are compared on the exact original
  100k-row split.
- New artifacts are stored in the behavioral-anomaly artifact set.
- The matched baseline reproduced the preserved baseline exactly: ROC-AUC
  `0.5774`, average precision `0.000366`, and zero fraud captured at top
  10/50/100/500.
- The first behavioral model scored ROC-AUC `0.5105`, average precision
  `0.000280`, and also captured zero fraud at top 10/50/100/500. This is a
  negative result on the 100k slice, not evidence that behavioral features are
  ineffective in general.
- The 1M-row matched experiment uses the same fixed Isolation Forest
  configuration for both models; no final-test tuning was performed.
- On 1M rows, the chronological split contains 699,825 training rows through
  step 36 and 300,175 test rows from step 37 onward, with 118 test fraud rows.
- PaySim account activity is highly asymmetric: only 241 of 999,759 origin
  accounts repeat, while 76,035 of 422,896 destination accounts repeat.
  Repeated origins account for `0.0482%` of rows; repeated destinations account
  for `65.3139%` of rows.
- Only 114 test rows (`0.0380%`) have a sender seen in training, while 154,110
  test rows (`51.3401%`) have a receiver seen in training. Sender-history
  features are therefore almost always zero; receiver-history features are
  nonzero for approximately `58.5%` of test rows.
- The 1M baseline scored ROC-AUC `0.6739`, average precision `0.003064`, and
  captured `0/0/0/2` frauds at top `10/50/100/500`.
- The 1M behavioral model scored ROC-AUC `0.6362`, average precision `0.012157`,
  and captured `1/2/3/6` frauds at top `10/50/100/500`. It improved average
  precision and alert-budget recall, but not ROC-AUC; this is a ranking
  trade-off, not universal model improvement.

### Tests and documentation baseline

Automated tests cover the generic supervised pipeline and ingestion adapter.
Project guidance, Module 1 guidance, next steps, and a development log are
present. The project contains the raw PaySim CSV, a 100k processed sample, and
saved model artifacts.

## Project scope and limitations

### Evaluation limitations

- The anomaly baseline test set contains only seven fraud examples, making
  ranking metrics unstable.
- The current anomaly experiment reports ROC-AUC, average precision, and a
  top-100 review result, but not a broader alert-budget curve or multiple fixed
  alert volumes.
- There is no validation split for selecting Isolation Forest hyperparameters or
  feature configurations.
- No paired comparison currently exists between the original and
  behavioral-feature models on the exact same rows and test steps.
- PaySim is simulated; results must remain explicitly limited to this benchmark.

### Module 3 feature gap

The behavioral experiment uses history, but its feature set and evaluation need
further improvement. It does not yet represent historical sender transaction
frequency, transaction velocity over prior hours or steps, historical average
transaction amount, amount deviation from an account's prior behavior, or
unusual sender/receiver or transaction-type patterns.

Raw PaySim identifiers are available in the source data but are intentionally
not used as baseline model predictors. A future feature-engineering path must
use them only to derive history-based aggregates and must not expose raw
identifiers as model predictors.

### Leakage and time semantics

- PaySim provides hourly `step` values but does not establish an ordering within
  an hour. Same-step transactions must therefore be treated as simultaneous for
  historical features.
- Behavioral features must be computed from strictly earlier steps. Current-step
  transactions must not contribute to their own history or to another
  transaction's history within the same step.
- Aggregates must be fit or updated in chronological order and evaluated only on
  information available before each test step.
- The anomaly baseline and supervised benchmarks use different sample sizes and
  split definitions, so direct metric comparisons require a deliberately matched
  experiment.

### Engineering limitations

- The anomaly experiment is a standalone analysis rather than a reusable
  feature-engineering module with unit tests.
- The behavioral feature path remains an evaluation prototype rather than a
  production component.
- The repository is not currently a local Git repository, so file history and
  change provenance cannot be inferred from Git metadata.
- The integrated risk engine, grounded retrieval layer, analyst dashboard,
  monitoring package, feedback store, and security test harness are local
  research-prototype components. They do not constitute a production
  deployment.
- Module 4 infrastructure, calibration utilities, and frozen holdout evaluation
  are present. Future work is limited to governed operational validation and
  deployment integration.

## Remaining roadmap

1. **Behavioral feature refinement:** focus on receiver-side history because
   sender identities are almost entirely one-shot in this PaySim slice. Use a
   chronological validation period for any feature or model configuration
   selection.
2. **Matched anomaly evaluation:** retain the completed 1M comparison as the
   current Module 3 reference and use future experiments only when they preserve
   identical rows, boundaries, and alert budgets.
3. **Evaluation expansion:** retain average precision, ROC-AUC,
   precision/recall at fixed alert counts, fraud captured in top 10/50/100/500
   alerts, and split/provenance metadata. Use validation data for configuration
   choices.
4. **Memory and reproducibility checks:** continue using compact dtypes, bounded
   columns, and step-wise processing appropriate for a 16 GB machine; record
   parameters and feature definitions in metrics JSON.
5. **Documentation synchronization:** keep the README, Module 3 documentation,
   and development log aligned with actual experiment dates and negative as well
   as positive results.
6. **Later modules:** add governed deployment integration, managed identity,
   locked dependencies, operational monitoring, and controlled retraining only
   after additional validation.

## Recommended implementation sequence

Before modifying existing experiments, the next versioned components should be
developed in this order:

1. A pure, testable behavioral-feature state-update component.
2. Unit tests for chronological behavior and leakage prevention.
3. A new experiment runner that leaves the existing Isolation Forest experiment
   and its artifacts unchanged.
4. A matched baseline-versus-behavioral report in a new artifact directory.
5. Documentation synchronization after the experiment and tests pass.

This sequence preserves the current baseline while making subsequent results
reproducible and directly comparable.
