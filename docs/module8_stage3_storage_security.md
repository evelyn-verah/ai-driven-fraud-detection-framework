# Module 8 Stage 3 — SQLite, Filesystem, and Artifact Security

Stage 3 adds security boundaries around the local prototype while preserving
the frozen Modules 4–7 artifacts and behavior. The implementation is in
`src/security/storage_security.py`; it is an adapter layer rather than a
change to the frozen monitoring lifecycle, dashboard, or risk model code.

## Trust boundaries and controls

* **SQLite (T04, T09, T10, T14):** feedback writes validate row IDs, status,
  reviewer-label and note bounds before delegating to the existing
  parameterized `save_review` implementation. Reads use a SQLite `mode=ro`
  URI, fixed-column queries, schema/field validation, and safe error text.
  Production-only wrappers reject the configured demonstration database.
* **Filesystem (T05, T08, T10, T11, T14):** `secure_path` canonicalizes
  paths, confines them to an explicitly trusted root, rejects symlinks and
  type confusion, and rejects control characters. `publish_json` uses an
  exclusive temporary file and no-clobber publication. Output collisions,
  parent traversal, and unavailable roots fail closed.
* **Serialized artifacts (T06, T07, T08):** `verify_serialized_artifact`
  requires a trusted root, supported joblib/pickle suffix, and SHA-256 match
  before `safe_load_joblib` invokes deserialization. A checksum establishes
  identity relative to a trusted reference; it does not make pickle/joblib
  intrinsically safe. Arbitrary user-supplied serialized files remain
  unsupported.

## Validation

`tests/test_module8_stage3_storage_security.py` covers valid and malformed
SQLite databases, SQL-injection-shaped data, read-only behavior, demo/production
isolation, traversal, symlink escapes where the host permits symlink creation,
invalid file types, no-clobber output publication, checksum mismatch and safe
artifact loading, safe errors, and frozen artifact preservation.

Focused Stage 3 plus adjacent regression tests: **57 passed, 1 skipped**.
The complete project suite: **172 passed, 1 skipped**.

Frozen SHA-256 values for the Module 4 score cache and Module 5, Module 6, and
Module 7 manifests match their recorded values. Existing Module 7 monitoring
outputs remain covered by the Stage 5 reproducibility tests and were not
rewritten.

## Limitations

The legacy `FinalRiskAssessment.from_joblib_paths` and development evaluation
loader still exist for backward compatibility and perform direct loading;
secure callers must use the new verification boundary before constructing the
risk engine. Authentication, authorization, log redaction, and network/upload
controls are intentionally deferred to Module 8 Stage 4 or later. Symlink
negative tests may be skipped on hosts where the operating system denies
symlink creation.

## Reproduction

From the repository root in VS Code, run:

```text
python -m pytest -q tests/test_module8_stage3_storage_security.py
python -m pytest -q
```

The wrappers are imported from `src.security.storage_security` and accept an
explicit trusted directory, so tests and local workflows can use temporary
synthetic roots without touching the clean production-like feedback database.
