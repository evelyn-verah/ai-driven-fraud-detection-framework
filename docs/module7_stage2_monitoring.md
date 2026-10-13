# Module 7 Stage 2 — Read-only monitoring

Stage 2 provides deterministic retrospective summaries over the validated Module 4 holdout score cache and, when requested, the Module 6 metadata sidecar. It does not rescore transactions, inspect ground-truth labels, modify frozen artifacts, or perform drift detection.

## Inputs and contracts

`src/monitoring/engine.py` loads the score cache through the existing dashboard validator and can validate the sidecar through `metadata_index`. The score contract requires `row_id`, `step`, `fraud_probability`, both anomaly intensities, `rule_score_context`, and the stored boolean `alert`. The internal `isFraud` alignment field is never copied into monitoring outputs. `MonitoringWindow` requires integer, complete-step bounds and a rationale; windows must be within steps 378–743 and cannot overlap.

## Metrics

The engine emits counts and rates overall and by step, transaction-type counts/proportions and amount statistics when sidecar metadata is supplied, score descriptive statistics and fixed 0.1 probability bins, and baseline/behavioral anomaly statistics with the same fixed bins. Alert counts use the stored frozen decision. The frozen threshold is reported for context and used only for an above-threshold descriptive count; it is never recalibrated. Missingness is reported explicitly. Anomaly intensities are contextual indicators, not fraud probabilities.

## Outputs and reproducibility

Results use schema `module7_stage2_monitoring_v1`, include source paths/checksums, Module 4 architecture and threshold, windows, limitations, and a UTC execution timestamp. `write_monitoring_result` writes JSON through a temporary file and atomic replace. Output artifacts contain no `isFraud`, account identifiers, or analyst notes. A small validation result is published at `artifacts/module7_stage2_monitoring/stage2_validation_subset.json`; it is descriptive evidence only and is not a new model evaluation.

## Validation and performance

Complete-step validation is enforced by requiring authoritative per-step counts. A window is publishable only when every inclusive step has an expected count and the observed score rows match that count; duplicate row IDs, missing steps, or partial step subsets fail clearly. The final validation used step 378 from the frozen score cache: expected and observed transaction count **37,127**, expected and observed alert count **5**, alert rate **0.00013467287957551107**, and frozen threshold **0.3494391872980995**. All 37,127 metadata rows aligned by row ID and step; score and anomaly fields had zero missing values. The run completed in approximately 3.54 seconds after loading the validated cache and sidecar once, without processing raw PaySim rows. Focused monitoring tests cover counts, rates, quantiles/bins, anomaly missingness, metadata alignment, malformed and duplicate inputs, invalid and partial windows, deterministic calculations, label-free serialization, and atomic publication failure. The complete project suite passed 119 tests.

## Limitations

These are retrospective summaries of simulated PaySim data. PaySim steps are simulation units, not calendar timestamps. No drift, feedback, independently verified labels, causal explanation, or real-world operational conclusion is produced. Future stages must keep monitoring read-only and preserve the frozen Random Forest decisions.

## Reproduction

From the repository root, run `python -m pytest tests/test_monitoring_stage2.py`. To build a summary, import `load_frozen_inputs`, select explicitly approved complete-step windows, call `summarize_monitoring`, and publish with `write_monitoring_result`.
