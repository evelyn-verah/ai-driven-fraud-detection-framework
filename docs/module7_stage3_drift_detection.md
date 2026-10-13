# Module 7 Stage 3 — Data and prediction drift

Stage 3 adds a read-only descriptive comparison over frozen Module 4 outputs and the validated Module 6 metadata sidecar. It does not retrain, rescore, recalibrate, tune the alert threshold, or use PaySim labels.

## Window rules

`analyze_drift` requires two explicit `MonitoringWindow` values. The reference window must end before the comparison window begins. Both windows must be non-overlapping, inside steps 378–743, and complete: every inclusive step must have an authoritative expected row count, and observed score rows must match it exactly. Duplicate row IDs, missing steps, partial steps, invalid scores, or misaligned metadata fail before metrics are calculated. The source step counts come from the validated frozen score cache.

The bounded validation uses steps **378** and **379**. These were selected before inspecting results: step 378 is the earliest complete final-holdout step and step 379 is the immediately following complete step. This is a descriptive adjacent-window check, not an outcome-based window or threshold selection procedure.

## Metrics

Continuous features include transaction amount (when sidecar metadata is present), baseline anomaly intensity, behavioral anomaly intensity, and fraud probability. The implementation reports:

- Two-sample Kolmogorov–Smirnov empirical distance.
- Population Stability Index using fixed bins. Probability and anomaly bins are 0.1-wide on [0, 1]; amount bins are [0,1), [1,10), [10,100), [100,1000), [1000,10000), and [10000,∞).
- Missingness counts, rates, and rate changes.

Transaction type uses Jensen–Shannon divergence over the union of levels. A level present in only one window is retained with a zero count in the other. Prediction drift also reports frozen alert counts/rates, counts above the unchanged threshold, and probability quantiles/fixed-bin comparisons.

PSI uses an epsilon of 1e-12 for numerical stability. Empty or all-missing samples return no distance rather than a fabricated zero. Constant distributions are valid and produce zero when identical. No metric is treated as a significance test or automatic model-degradation decision; interpretation depends on bins, sample size, missingness, and distribution assumptions.

## Validation

The bounded run compared **37,127** transactions in step 378 with **41,759** in step 379. Alerts were 5 and 26 respectively. The alert-rate change was 0.0004879473938984706. Fraud-probability KS was 0.0032927411018629504 and PSI was 0.0037611085021947016. Amount PSI was 0.0015197904871388267 and transaction-type Jensen–Shannon divergence was 1.96443372966242e-05. The run completed in approximately 4.03 seconds after one validated cache/sidecar load. Results are in [stage3_step378_vs_379.json](../artifacts/module7_stage3_drift/stage3_step378_vs_379.json).

Synthetic tests cover identical and shifted distributions, missing categories, zero-frequency bins, missing values, constant values, invalid ordering, overlap, partial steps, duplicates, metadata misalignment, deterministic calculations, and label-free output. The complete project suite passed 127 tests after Stage 3 additions.

## Limitations and reproduction

These are retrospective comparisons of simulated PaySim step units, not calendar-time monitoring or evidence of real-world degradation. Drift does not imply fraud, a changed fraud prevalence, or a failed model. Future work may add predeclared reference governance, statistical confidence procedures, and dashboard presentation without changing frozen Module 4 decisions.

From the repository root, run `python -m pytest tests/test_monitoring_stage3.py` for focused tests. Use `load_frozen_inputs`, define ordered complete windows and the source step-count map, call `analyze_drift`, and publish with `write_monitoring_result`.
