# Module 4 — Integrated Transaction Risk Assessment

## Current implementation status

Stages 1 and 2 are implemented. Stage 3 development calibration and comparison are now complete;
the final holdout remains untouched. Results are in
`artifacts/module4_development_v1/development_results_v3.json`.

### Chronology reconciliation

The supervised 1M-row benchmark reported 140,713 transactions in steps 42–45 because it read only the first 1,000,000 CSV rows. That sample ended partway through step 45. The full PaySim file contains 143,387 transactions across complete steps 42–45. The difference is 2,674 rows from the remainder of step 45 in the full file. These counts are not contradictory; one is a bounded prefix and the other is the complete chronological period.

## Frozen evaluation protocol

- Existing model training: steps 1–36.
- Existing supervised validation: steps 37–41. The saved Random Forest threshold was selected by maximum validation F1; these steps are not reused for Module 4 fusion calibration.
- Steps 42–45: diagnostic-only because they were previously examined.
- Module 4 development/calibration: steps 46–377.
- Calibration: steps 46–200.
- Development evaluation: steps 201–377.
- Untouched temporal holdout: steps 378–743.

The development and final boundaries are based on chronological row counts and whole-step boundaries, not model performance. The final holdout will not be scored or evaluated until the integrated system is frozen.

## Stage 1 components

- `src/risk_engine/contracts.py` validates PaySim transaction-time fields.
- `src/risk_engine/behavioral_state.py` provides a stateful, step-batched processor and a chunked complete-step CSV iterator.
- `src/risk_engine/scorers.py` adapts the frozen supervised and Isolation Forest artifacts while preserving their exact feature contracts.

The behavioral processor updates account state only after a complete step is transformed. It therefore prevents same-hour visibility and future leakage. Tests compare it against the existing batch implementation.

## Stage 2 components

- `src/risk_engine/rules.py` contains transparent PaySim-supported rules and rule identifiers.
- `src/risk_engine/normalization.py` provides empirical-CDF normalization that must be fitted on development scores.
- `src/risk_engine/fusion.py` combines bounded supervised, anomaly, and rule signals using explicit configurable weights.
- `src/risk_engine/decisions.py` produces bounded risk scores, low/medium/high tiers, alert decisions, and component/rule explanations.

Stage 3 calibration parameters were fitted on steps 46–200 for the development
comparison. The final architecture does not use fusion weights or anomaly
normalization to drive alerts; it freezes the Random Forest threshold from that
calibration and keeps anomaly values independent.

## Stage 3 preparation

- `src/risk_engine/development_pipeline.py` performs one chronological pass and writes a versioned aligned
  cache containing supervised, baseline-anomaly, behavioral-anomaly, rule, label, and rule-provenance fields.
- The cache writer processes history through step 45, scores only steps 46–377, writes one complete step at a time,
  and refuses to overwrite an existing cache by default.
- Fusion configurations consume cached scores. They do not reconstruct behavioral history or rescore transactions.
- `fit_calibration_normalizers` and `calibrate_fusion` accept calibration rows only. `apply_calibration` applies
  the resulting frozen parameters and adds `no_elevated_contributing_signal_identified` when no explanation signal
  is present.
- `fit_fusion_weights` searches only a fixed, documented candidate set on calibration rows; it does not inspect
  development-evaluation or final-holdout labels.
- Profiling steps 1–55 processed 1,030,311 rows in 85.4 seconds; 82.5 seconds were behavioral processing and
  approximately 3.2 seconds were CSV parsing/boundary handling. The dominant memory pressure is the growing
  account-history dictionaries, not the one-step chunk buffer.

## Testing

Recovery validation on 2026-10-11: the full repository suite passes **41 tests**.
Direct normalizer fitting and weight selection now enforce calibration step
boundaries, with explicit `split=` arguments for custom fixture intervals.
Maximum-F1 threshold selection uses sorted cumulative counts rather than
rescanning every row for every threshold. Regression tests preserve the original
tie and endpoint behavior. The following count describes the earlier checkpoint.

The Stage 3 and Stage 4 suites cover chunk-boundary correctness, score-cache
alignment and reproducibility, calibration-range enforcement, score bounds,
explanation provenance, same-step isolation, increasing-step enforcement,
batch/streaming feature equivalence, RF ranking consistency, target isolation,
threshold decisions, and independent anomaly/rule evidence. The Stage 3
development model comparison is saved under `artifacts/module4_development_v1`;
the final temporal holdout remains pending approval.

## Limitations

The development comparison did not improve ranking over Random Forest alone. Random Forest alone achieved
average precision 0.5932 and ROC-AUC 0.9940. Baseline anomaly achieved 0.4659/0.8561, behavioral anomaly
0.4196/0.8270, both anomalies 0.3762/0.7891, and anomalies plus rules 0.1051/0.6806. At 500 alerts,
Random Forest captured 496 frauds, baseline anomaly 498, behavioral anomaly 498, both anomalies 498,
and rules 248. These are simulated PaySim development results and do not justify production claims.

PaySim is simulated. These components and future results are engineering benchmarks, not evidence of production fraud-detection effectiveness. The frozen models were trained only on steps 1–36, so results on steps 378–743 will measure temporal generalization as well as integration quality.

## Stage 4 — Final architecture implementation

`src/risk_engine/final_architecture.py` implements version
`module4_stage4_rf_primary_v1`. `FinalRiskAssessment.assess_step` accepts one
complete chronological transaction step and returns aligned rows containing:

- `fraud_probability`: the frozen Random Forest probability;
- `baseline_anomaly_intensity` and `behavioral_anomaly_intensity`: independent
  Isolation Forest intensities, where higher means more anomalous; these are not
  calibrated fraud probabilities;
- `triggered_rules` and `rule_score_context`: transparent contextual evidence;
- `alert`: `fraud_probability >= 0.3494391872980995`;
- `explanation`: human-readable provenance for the probability, anomaly evidence,
  rules, and threshold.

The alert threshold is frozen from maximum-F1 calibration on steps 46–200. It is
recorded with provenance in `FinalRiskAssessmentConfig`; anomaly and rule values
cannot modify or override the Random Forest probability or alert decision. The
behavioral processor transforms a complete step before committing state, so
same-step history cannot leak into features. Model versions and architecture
metadata are immutable configuration fields. Stage 4 validation added five tests
for ranking consistency, threshold decisions, score alignment, target isolation,
same-step history, explanation behavior, and reproducibility.

## Holdout recovery mechanism

The interrupted holdout prefix remains immutable at
`artifacts/module4_final_holdout_v1/holdout_scores.csv`. The new
`src/risk_engine/holdout_recovery.py` module prepares a separate versioned
recovery directory. It verifies prefix row counts, source order, labels, score
finiteness, frozen model hashes, feature definitions, architecture version, and
threshold provenance before any resume. It replays behavioral history through
step 428 without rescoring the preserved prefix, then writes missing suffix
steps as atomic per-step checkpoints with an atomically updated manifest.

The 428-to-429 boundary has a deterministic equivalence test against an
independent chronological reference. Final combination refuses incomplete
steps, duplicate or non-sequential row IDs, invalid labels, and non-finite
scores; metrics are exposed only after this integrity gate passes. The mechanism
has been tested, but the remaining holdout scoring run has not been launched.

The actual prefix verification passed: 597,486 rows align with raw steps
378–428, all prefix labels and row order match, the frozen model hashes and
feature definitions match the Stage 4 manifest, and the threshold remains
0.3494391872980995. No recovery output directory has been initialized.
### Final temporal holdout recovery

Recovery artifact: `artifacts/module4_final_holdout_recovery_v1/`. The immutable steps 378–428 prefix was reused and steps 429–743 were scored with atomic complete-step checkpoints.

The final holdout contains 955,744 transactions and 4,010 frauds. Average precision is 0.747744 and ROC-AUC is 0.992739. At the frozen Random Forest threshold 0.3494391872980995, precision is 0.908425, recall 0.556608, and F1 0.690274 (TP 2,232; FP 225; FN 1,778; TN 951,509). The recovery took 5,575.22 seconds; observed reconstruction RSS was approximately 1.95 GB. Full source alignment and cache integrity checks passed.
