# Development log

## 2026-10-11 — Shutdown recovery and calibration hardening

Inspected the supplied read-only conversation snapshot, implementation records,
source, tests, and artifact inventory. Recovered Module 4 Stage 3 preparation;
no completed Stage 3 cache or experiment was present. The initial suite passed
27 tests. Added six regression cases demonstrating that direct normalization and
weight-selection helpers accepted diagnostic, evaluation, and holdout steps.
Both helpers now enforce the calibration split, including explicit custom test
splits. Replaced quadratic threshold rescanning with sorted cumulative counts;
regressions verify equivalence to exhaustive threshold selection for tied scores,
mixed labels, and single-class labels. The full suite now passes 36 tests.

No saved benchmark artifacts or input data were changed. Full development
calibration and final evaluation remain pending. The next work is an experiment
runner with durable cache-completion metadata, followed by the development-only
comparison under the recorded split protocol.

## 2026-10-11 — Module 4 Stage 3 development evaluation

Ran the frozen development-only pipeline through step 377. Calibration covered
steps 46–200 and evaluation covered steps 201–377; the final holdout beginning at
step 378 was not read. The score cache contains 1,379,508 calibration rows and
3,024,694 evaluation rows. Five predeclared fusion configurations reused the same
cache, with anomaly normalizers and alert thresholds fitted only on calibration
rows. Random Forest alone was the strongest ranker (average precision 0.5932,
ROC-AUC 0.9940). Baseline anomaly slightly improved the 500-alert capture (498
versus 496) but lowered both ranking metrics; behavioral anomaly, both anomalies,
and rules did not improve the baseline ranking. The source pass took 2,215 seconds
and the active process reached approximately 1,610 MB resident memory. Results
are saved under `artifacts/module4_development_v1`.

## 2026-10-10 — Phase 1 baseline scaffold
- Created synthetic engineering fixture, preprocessing, two supervised baselines, held-out metrics, model serialization, and automated tests.
- **Synthetic dataset only** in initial smoke test; not a claim of performance on real transaction data.
- Next: source and validate a licensed, real-world labeled fraud dataset, audit leakage, and build temporal holdout evaluation.

## 2026-10-10 — Module 1 ingestion adapter
Added PaySim schema validation, bounded inspection, conservative feature preparation, tests, and explicit real-data instructions. No external PaySim data supplied or trained in this update.

## 2026-10-11 — Module 3 behavioral analytics increment
Added chronological, step-batched PaySim behavioral features and tests for same-step leakage prevention. Added a versioned matched Isolation Forest experiment under `artifacts/anomaly_detection_behavioral`; the original Module 3 script and artifacts were preserved. On the matched 100k-row benchmark, the first behavioral feature set underperformed the original baseline, so further validation and feature refinement are required. PaySim remains simulated and no production claim is made.
