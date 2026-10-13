# Module 7 V1 validation and freeze

Module 7 is frozen as `module7_v1_frozen`. The freeze manifest is
[module7_v1_freeze_manifest.json](../artifacts/module7_v1_freeze_manifest.json).

## Validation scope

The validation inspected all Module 7 monitoring source files, Stage 2–5
tests, contracts, documentation, configuration, and the completed Stage 5
manifest. A new run named `stage6_validation_step378_vs_379_20261013` was
published without overwriting either completed Stage 5 run.

The runner loaded the frozen score cache and metadata sidecar once. It did not
read the raw PaySim CSV, use fraud ground-truth labels for monitoring decisions,
retrain a model, or modify the frozen threshold.

## Independent results

The frozen score cache independently produced:

| Window | Transactions | Alerts |
| --- | ---: | ---: |
| Step 378 | 37,127 | 5 |
| Step 379 | 41,759 | 26 |

Independent recomputation matched the runner outputs:

- Fraud-probability KS: `0.0032927411018629504`
- Fraud-probability PSI: `0.0037611085021947016`
- Amount PSI: `0.0015197904871388267`
- Transaction-type Jensen–Shannon divergence: `1.964433729665564e-05`
- Score and metadata missing values: `0`
- Feedback events: `0`
- Feedback database remained byte-for-byte unchanged after read-only access.

The small floating-point difference between the independently computed
Jensen–Shannon value and the runner value (`1.96443372966242e-05`) is due to
the independent calculation library's numerical implementation; the values
agree at the reported scale.

## Integrity and privacy

Complete-step enforcement, reference-before-comparison ordering, score/sidecar
row alignment, alert decisions against threshold `0.3494391872980995`, output
checksums, and run-ID collision protection all passed. Monitoring outputs were
checked for exclusion of `isFraud`, `isFlaggedFraud`, sender/receiver account
identifiers, reviewer identities, and free-text notes.

The Module 4 score cache and recovery manifest, Module 5 freeze manifest, and
Module 6 freeze manifest retain their recorded SHA-256 checksums. No Module 4–6
file was changed.

## Tests and reproduction

Focused Module 7 validation passed **30 tests** across Stages 2–5. The full
project suite passed **141 tests**.

From the repository root, reproduce a new run with:

```powershell
python -c "from src.monitoring.lifecycle import load_config, run_monitoring; run_monitoring(load_config('configs/module7_stage5_monitoring_v1.json'))"
```

Completed run IDs are immutable. Choose a new run ID for a subsequent run;
reproducible calculations should match after run-specific timestamps and
filesystem metadata are removed.

## Limitations

PaySim is simulated. Drift statistics are descriptive comparisons rather than
significance tests or evidence of model degradation. Analyst feedback remains
mutable workflow information, not verified fraud ground truth. This freeze
covers offline retrospective monitoring only; MLflow, retraining, and Module 8
are outside the V1 scope.
