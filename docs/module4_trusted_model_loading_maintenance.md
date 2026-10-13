# Module 4 Trusted Model Loading Security Maintenance

This separately versioned maintenance release routes the two supported Module
4 model-loading paths through trusted artifact verification. It does not change
model features, thresholds, scoring, alert semantics, evaluation data, or any
serialized artifact.

## Updated paths

* `FinalRiskAssessment.from_joblib_paths` in
  `src/risk_engine/final_architecture.py` now calls `load_trusted_model` for
  the three frozen model artifacts.
* `src/risk_engine/run_development_evaluation.py` now calls the same trusted
  loader for its three fixed development model paths.

The only remaining `joblib.load` call in the source tree is inside the Stage 3
`safe_load_joblib` implementation, after path and checksum verification.

## Trusted checksum source

`src/risk_engine/trusted_artifacts.py` contains a versioned role-to-path and
SHA-256 mapping matching `frozen_manifest.model_sha256` in
`artifacts/module4_final_holdout_recovery_v1/recovery_manifest.json`:

* supervised: `0292f5ea763cf436bbf324b7d8f028a3791f9c31927717bd9026afaedecffbf5`
* baseline anomaly: `30b5c1d8d18a1a84ba4dc8b176f35377567f88130c77e555064ac70e2983b59a`
* behavioral anomaly: `8fa657f3224918e7aa324b76a8f526818e2ade669db352a6eb7b60ec2fa75173`

Callers cannot supply a checksum, role, or arbitrary path. Missing, modified,
unexpected, or symlinked artifacts fail before deserialization. SHA-256 detects
modification relative to the trusted baseline; it does not independently prove
that a Python serialized object is safe.

## Provenance and validation

The original frozen `final_architecture.py` hash was
`d531f6e8d0f84f092e048a930fee1b830a7e7330fd90c3609c98e3790d62332d`. The
development-loader pre-maintenance hash was
`0aec8894f0e2814073453cf21bbfa7501635ab947ddd457f49e0b3b113e182d6`.
Updated hashes and historical references are recorded in the maintenance
manifest.

The focused risk/security set passed **81 tests with 1 symlink skip**. The full
project suite passed **203 tests with 1 skip**. No malicious payloads were
created or loaded, and frozen Module 4–7 artifacts and outputs remain
unchanged.

Production should additionally use authenticated manifests, artifact signing,
isolated deserialization, dependency locking, and deployment identity controls.
