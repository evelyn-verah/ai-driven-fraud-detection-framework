# Module 7 Stage 5 — Monitoring lifecycle and reproducibility

Stage 5 adds a versioned, read-only runner that composes the existing Stage 2
summaries, Stage 3 drift analysis, and Stage 4 feedback analysis. It loads the
validated frozen score cache and metadata sidecar once, never reads the raw
PaySim CSV, and never retrains, rescales, or changes the Module 4 threshold.

## Configuration contract

`configs/module7_stage5_monitoring_v1.json` uses schema
`module7_stage5_monitoring_config_v1`. It declares a path-safe run ID, ordered
complete-step reference and comparison windows, summary windows, the frozen
architecture and threshold, score-cache and metadata-sidecar paths, optional
feedback settings, and an output directory. Validation rejects missing sources,
threshold or architecture mismatches, windows outside steps 378–743, duplicate
or overlapping windows, and an unordered drift pair.

## Reproduce the bounded run in VS Code

From the repository root, run:

```powershell
python -c "from src.monitoring.lifecycle import load_config, run_monitoring; run_monitoring(load_config('configs/module7_stage5_monitoring_v1.json'))"
```

Each run publishes a new directory named for its run ID. Completed run
directories are immutable; reusing a run ID fails instead of overwriting it.
The manifest records configuration and schema versions, UTC timestamps, frozen
input checksums, output checksums, runtime, status, and limitations. A failed
run records its error in `manifest.json`.

## Bounded validation

The validation run compared step 378 with step 379. Independent score-cache
counts are 37,127 transactions and 5 alerts for step 378, and 41,759
transactions and 26 alerts for step 379. The production-like feedback database
was read through the Stage 4 read-only interface and contained zero events.
No fraud labels were used for monitoring decisions or tuning.

Outputs are separate `monitoring.json`, `drift.json`, `feedback.json` (when
enabled), and `manifest.json` files under the versioned run directory. They
exclude fraud labels, account identifiers, reviewer identities, and free-text
notes. Feedback statuses remain workflow assessments, not verified outcomes.

## Validation commands

```powershell
python -m pytest -q tests/test_monitoring_stage5.py
python -m pytest -q
```

This stage remains a retrospective research workflow over simulated PaySim
data. It does not establish production performance, detect verified fraud, or
provide online alerting. MLflow, retraining, and Module 8 work are outside
Stage 5.
