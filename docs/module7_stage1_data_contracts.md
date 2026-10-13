# Module 7 Stage 1: Data Contracts

The contracts below describe fields that exist today or are explicitly marked future-only. They are proposed interfaces; this stage does not implement monitoring calculations.

## Monitoring transaction record

Required: `row_id` (non-negative integer), `step` (integer), `fraud_probability` (finite float in [0,1]), `baseline_anomaly_intensity` (finite float in [0,1]), `behavioral_anomaly_intensity` (finite float in [0,1]), `rule_score_context` (finite float in [0,1]), and `alert` (boolean). Optional metadata includes `type`, `amount`, and balance fields from the validated sidecar. `isFraud` may be retained only for internal source-alignment validation and must be excluded from analyst-facing monitoring features.

Provenance must identify the Module 4 score-cache path/checksum, architecture version, threshold, sidecar version/checksum when metadata is used, and complete step range. Records are immutable inputs.

## Monitoring window

Required: `window_id`, `start_step`, `end_step`, `purpose`, `selection_rationale`, `created_at_utc`, and source versions. Bounds must be integers, complete, ordered steps, and within the declared source period. A window definition is immutable after publication.

## Reference-period definition

Required: `reference_id`, source artifact checksum, complete-step bounds, population description, and rationale selected before outcome inspection. Optional stratification includes transaction type. It must not include future data relative to the current window or final-holdout outcomes used for tuning.

## Summary metrics

Transaction/alert summaries contain counts, alert rate, transaction-type counts, amount count/min/median/max or bounded quantiles, and missingness counts. Score summaries contain count, mean, median, quantiles, and bounded high-risk counts. Anomaly summaries retain their names and explicitly state that anomaly intensities are not fraud probabilities.

## Drift metric

Required: metric name, variable, reference/current window IDs, sample counts, value, method version, and interpretation. PSI is appropriate for predeclared bins with sufficient counts; KS is suitable for continuous distributions with adequate samples; Jensen–Shannon divergence is suitable for categorical distributions. Missingness change is reported separately. Small samples, bin choices, dependence, and multiple comparisons must be documented. No metric automatically indicates model degradation.

## Analyst feedback summary

Required: database path/checksum at read time, window bounds, event count, status counts, reviewer-label count, and timestamp range. Optional backlog counts are defined from statuses. `False Positive Suspected` and `Escalated` remain analyst assessments, not truth labels. Feedback is mutable and is never part of the immutable Module 6 freeze.

## Independently verified labels (future-only)

Required: stable transaction identifier, verified label, verification authority/process, label timestamp, source checksum, and alignment evidence. The source must be independent of analyst opinion and joined without future leakage. Without these fields, precision, recall, F1, average precision, ROC-AUC, and confusion matrices are unavailable.

## Monitoring run and experiment metadata

Required: run ID, UTC timestamp, code/version hashes, Python/dependency versions, source manifests/checksums, window/reference IDs, parameters, output paths, validation status, and limitations. Experiment metadata must never imply that a monitoring comparison changed the frozen model.

## Monitoring finding/alert

Required: finding ID, run ID, finding type, metric, value, severity policy version, evidence window, explanation, and status. Findings are descriptive research outputs. They are not fraud labels, automatic model changes, or irreversible analyst actions.

