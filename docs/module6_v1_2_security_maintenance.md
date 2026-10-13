# Module 6 V1.2 Security Maintenance — Dashboard Authorization Integration

Module 6 V1.2 adds a separately versioned secure execution boundary and
migrates the supported Streamlit launcher without rewriting the historical V1
or V1.1 dashboard sources and manifests.

## Secure entry point

The entry point is [secure_app.py](../src/dashboard/secure_app.py). Its
`SecureDashboard` operations require an already issued Stage 4
`DashboardContext` before they call frozen data/detail code or the Stage 3
feedback writer:

* `load_scores` requires `dashboard.read` and returns the analyst-safe score
  projection.
* `load_transaction_detail` requires `transaction.detail` and applies the
  explicit detail projection before returning data.
* `submit_review` requires `review.submit` before writing feedback.
* `feedback_summary` requires `feedback.read` and returns only counts/statuses.
* `diagnostics` requires `diagnostics.read` and returns bounded non-sensitive
  cache diagnostics.

Missing, forged, unknown, or unauthenticated contexts fail before filesystem or
database access. The supported [app.py](../src/dashboard/app.py) launcher now
delegates to `streamlit_main` and fails closed when no trusted identity is
configured. Its pre-migration SHA-256 was
`d183f95ed9e0a45de1fdc2da385f88a7d52c2320abcc1fd6395d2b993ca71495`, matching
the recorded V1.1 corrected source hash. The migrated launcher hash and
supported command are recorded in the V1.2 maintenance manifest.

The archived V1 source snapshot is intentionally different and matches the V1
freeze hash `0818cf7b63dba59b54b86c493c9452e4a6dfb0930ebae73c4d6b13023d5ae647`;
the V1.1 corrected working-tree hash is the baseline being migrated.

## Identity limitation

The prototype has no authentication provider. `issue_local_context` is a
development-only test mechanism that requires an explicit trusted-local flag;
it must not be wired to a Streamlit widget, URL parameter, cookie, or caller
role string in deployment. A future identity-provider adapter must translate a
verified principal into a context outside the dashboard and reject missing or
expired sessions.

## Privacy boundary

The secure path excludes `isFraud`, `isFlaggedFraud`, `nameOrig`, `nameDest`,
reviewer identities, free-text notes, training labels, and unverified fraud
outcomes. Feedback is treated as mutable analyst workflow information.

## Validation and provenance

The integration tests are in
[test_module6_v1_2_security_integration.py](../tests/test_module6_v1_2_security_integration.py).
They cover unauthenticated denial, viewer reads and write denial, analyst
review writes, forged contexts, privacy, diagnostics, pre-access authorization,
and historical checksum preservation. The V1.2 maintenance manifest is
[module6_v1_2_security_maintenance_manifest.json](../artifacts/module6_v1_2_security_maintenance_manifest.json).

Historical V1 and V1.1 manifests remain unchanged. Module 4, Module 5, and
Module 7 artifacts remain read-only dependencies. This release does not change
scores, thresholds, retrieval, monitoring, model artifacts, or feedback schema.

## Known limitations

Historical source snapshots remain preserved and are not executable through the
supported launcher. A developer could intentionally import a preserved
snapshot directly, which is outside the supported command. Real authentication,
signed sessions, CSRF protection, deployment authorization, and model-loading
maintenance remain outside this release.
