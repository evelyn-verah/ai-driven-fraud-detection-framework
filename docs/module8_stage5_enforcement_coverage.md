# Module 8 Stage 5 — Security Enforcement Coverage

This matrix records actual call paths, rather than treating an available
wrapper as universal enforcement. The frozen Module 6 dashboard and Module 4
risk loaders are intentionally unchanged.

| Entry point | Trust boundary / threats | Existing control | Actually invoked? | Bypass / status | Tests |
|---|---|---|---|---|---|
| `src/dashboard/app.py::_cached_score_data` → `load_score_cache` | Local score-cache path; T05, T08, T10 | Score schema, threshold, alignment validation | Yes in legacy app | No Stage 4 context check; **partially enforced** | Dashboard data-access, Stage 4, Stage 5 |
| `src/dashboard/app.py::build_transaction_details` | Selected row and raw metadata; T01, T02, T03, T10 | Row/alignment checks and safe display mapping | Yes in legacy app | Direct Streamlit path bypasses facade; **partially enforced** | Dashboard details, Stage 4, Stage 5 |
| `src/dashboard/app.py::save_review` | Analyst-controlled review fields/database path; T04, T09, T12 | Stage 3 wrapper exists | No | Legacy direct write remains; **available but not integrated** | Feedback, Stage 3, Stage 5 |
| `src/dashboard/app.py::latest_review/review_history` | Feedback identities/notes; T01, T09, T10 | Existing raw event objects | No | Legacy UI displays reviewer and notes; **not enforced** | Stage 4 proves facade only |
| `src/security/dashboard_access.py::authorized_*` | Local caller context; T01, T02, T09, T12, T13 | Marker, role/permission checks, explicit projections | Yes when called | Legacy app does not call it; **enforced at facade boundary** | Stage 4, Stage 5 |
| `src/risk_engine/final_architecture.py::from_joblib_paths` | Serialized model paths; T06, T07, T08 | Source-controlled exact paths/checksums via `load_trusted_model` | Yes | No direct deserialization bypass remains; **enforced** | Module 4 trusted-loading tests |
| `src/risk_engine/run_development_evaluation.py::main` | Development model paths; T06, T07, T08 | Same trusted loader and frozen checksums | Yes | No direct deserialization bypass remains; **enforced** | Module 4 trusted-loading tests |
| `src/security/storage_security.py::safe_load_joblib` | Explicit trusted root/checksum; T06, T07, T08 | Canonical path, suffix, SHA-256 before load | Only callers that opt in | Does not intercept legacy loaders; **available but not integrated** | Stage 3, Stage 5 |
| `src/monitoring/lifecycle.py::run_monitoring` | Configured input/output paths; T05, T08, T10 | Lifecycle validation, atomic JSON, collision checks | Yes in monitoring runner | Does not use Stage 3 trusted-root facade; **partially enforced** | Monitoring Stage 5, Stage 5 |
| `src/monitoring/feedback.py::load_feedback_events` | Feedback DB; T04, T09, T10 | Read-only SQLite and schema validation | Yes in monitoring | Caller can supply arbitrary path; **partially enforced** | Monitoring Stage 4, Stage 3 |
| `src/ingestion/adapters.py::inspect_csv/prepare_paysim` | Local CSV/dataframe; T03, T11, T14 | Stage 2 schema, size, finite-value checks | Yes | CLI output path remains direct; **partially enforced** | Ingestion, Stage 2, Stage 5 |
| `src/dashboard/data_access.py::lookup_metadata` | Raw PaySim path/row IDs; T01, T03, T05 | Alignment and allowlisted columns | Yes in details | Arbitrary raw path accepted by legacy caller; **partially enforced** | Dashboard, Stage 5 |
| `src/fraud_intelligence/retrieval.py::build_retrieval_index` | Knowledge-base files; T05, T08 | Manifest/version/checksum and schema checks | Yes in app | No Stage 3 path confinement; **partially enforced** | Retrieval regressions |

## Required remediation

The dashboard bypasses require a separately versioned Module 6 security
maintenance release or a new secure Streamlit entry point. Direct model loads
require a versioned risk-engine maintenance release that routes trusted model
paths through checksum verification. Neither change is made in Stage 5 because
both would alter frozen baselines.

Production also requires real identity, signed sessions, CSRF protection,
authorization at the request boundary, protected logs, dependency locking, and
artifact signing or an equivalent authenticated provenance mechanism.
