# AI-Driven Fraud Detection framework

This repository is a local research prototype built around simulated PaySim
transactions. It contains the completed eight-module architecture: ingestion,
supervised and anomaly baselines, integrated risk assessment, grounded fraud
intelligence, an analyst dashboard, monitoring and reproducibility, and
cybersecurity testing.

The current release freezes Module 7 as `module7_v1_frozen` and Module 8 as
`module8_v1_frozen`. Module 6 V1.2 provides the supported fail-closed dashboard
launcher, and the Module 4 maintenance release verifies trusted model artifacts
before deserialization. 
## Quick start

```bash
python -m pip install -r requirements.txt
python -m pytest -q
```

The current full-suite result is **233 passed, 1 skipped**. The skip is a
Windows-host-dependent symlink test. Tests use synthetic fixtures where possible
and do not require the raw PaySim CSV.

To run the generic synthetic pipeline:

```bash
python -m src.fraud_detection.pipeline --out artifacts
```

The included synthetic data is generated from hand-coded rules. Its metrics do
not establish real-world fraud-detection effectiveness, transferability, or
production readiness.

## Dashboard and monitoring

The supported dashboard entry point is:

```bash
streamlit run src/dashboard/app.py
```

The launcher fails closed unless a trusted identity context is configured. It
does not provide production authentication or enterprise RBAC.

Module 7 monitoring is reproducible from the versioned configuration in
`configs/module7_stage5_monitoring_v1.json`. The frozen monitoring outputs and
manifest are under `artifacts/module7_stage5_monitoring/`.

## Repository contents

- `src/`: ingestion, models, risk engine, dashboard, monitoring, and security
  boundaries.
- `tests/`: unit, integration, reproducibility, and security regression tests.
- `docs/`: module architecture, contracts, validation reports, and limitations.
- `artifacts/`: frozen manifests, checksums, metrics, and small model artifacts.
- `configs/`: versioned monitoring configuration.

Raw datasets, local databases, logs, generated score tables, and other large
tabular exports are intentionally excluded by `.gitignore`. Obtain any legally
usable dataset separately and review its license, privacy, and leakage risks
before use. Do not load `.joblib` or pickle files from untrusted sources.

## Research-prototype limitations

This is not a production financial platform. It lacks managed identity,
signed sessions, enterprise RBAC, signed artifact provenance, fully locked
dependencies, and isolated hostile-object deserialization. Model and monitoring
results are frozen research artifacts over simulated PaySim data; no retraining,
MLflow workflow, or deployment integration is included.
