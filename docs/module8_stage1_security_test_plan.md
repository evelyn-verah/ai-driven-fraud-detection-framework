# Module 8 Stage 1 — Security testing plan

This plan uses only local code and synthetic fixtures. It does not scan a
third-party service or network. Tests must run in temporary directories and
isolated subprocesses where a failure could affect process state.

## Test principles

- Treat security tests as negative contract tests: malformed or unauthorized
  actions must fail closed.
- Never use real credentials, external endpoints, or production data.
- Preserve frozen artifacts by copying inputs to a temporary fixture before any
  mutation test.
- Assert both the exception/result and the absence of side effects, sensitive
  output, or partial files.
- Keep ground-truth labels available only to internal alignment fixtures; never
  make them a decision feature or analyst output.

## Traceability matrix

| Threat | Component/interface | Preconditions | Proposed local test | Expected secure behavior | Severity | Acceptance criterion | Planned stage |
| --- | --- | --- | --- | --- | --- | --- | --- |
| T01 | Streamlit entry point | Dashboard process reachable | Unauthenticated request/role fixture | Access denied until identity and role are established | Critical | Protected routes have explicit deny-by-default tests | 4 |
| T02 | `analyst_display_scores`, details, monitoring JSON | Internal labels/accounts exist in fixtures | Recursive forbidden-field scan, including errors | No labels, account IDs, reviewer fields, or notes | High | Zero forbidden keys/values in every analyst-facing path | 2/4/5 |
| T03 | ingestion adapters and `validate_transactions` | Synthetic malformed/large frames | Missing columns, NaN/inf, negative, wrong dtype, oversized fixtures | Reject before model call; bounded work | High | All invalid fixtures rejected without writes | 2 |
| T04 | `feedback_store.py` | Temporary SQLite database | Quotes, SQL metacharacters, invalid status/IDs, concurrent writes | Parameterized atomic operation; no query alteration | High | Schema and unrelated rows unchanged | 3 |
| T05 | lifecycle/config/path readers | Temporary roots, symlinks, traversal strings | `..`, absolute outside root, symlink, existing output | Reject escape and no-clobber | High | Resolved paths remain inside approved roots | 3 |
| T06 | score/sidecar/KB manifests | Copied frozen fixtures | Flip bytes, swap manifest/checksum/version | Fail closed before use | Critical | Tampering produces a validation error and no output | 3 |
| T07 | model artifact loading | Isolated subprocess and copied artifact | Invalid/hostile serialized object and invalid prediction shape | Refuse untrusted artifact; process remains isolated | Critical | No application code execution or accepted invalid score | 3 |
| T08 | Stage 5 JSON config | Temporary config copies | Threshold/model/path/schema/unknown-key mutation | Reject before input load | High | Approved threshold and model identity are immutable | 3 |
| T09 | review database | Temporary database with events | Delete/update/replay/clock mutation | Unauthorized change detected or rejected; audit evidence retained | High | Append-only integrity check catches mutation | 3/4 |
| T10 | exceptions/logs/artifacts | Sensitive synthetic values | Trigger failures and capture output | Redacted bounded diagnostics | High | Forbidden-field scanner passes success/failure outputs | 4/5 |
| T11 | CSV/Parquet/JSON/Streamlit | Large synthetic inputs | Size, cardinality, decompression, repeated request fixtures | Quota/rejection before exhaustion | High | Memory/time/output budgets enforced | 2/5 |
| T12 | requirements/build environment | Offline package metadata | Lock/checksum/SBOM/advisory review | Only approved reproducible dependencies | High | Build inventory and exceptions are recorded | 5 |
| T13 | dashboard actions | Synthetic users/roles | Direct read/write calls under each role | Unauthorized operations denied and audited | Critical | Complete role/action negative matrix passes | 4 |
| T14 | CLI/future upload boundary | Temporary upload staging | Symlink, polyglot, traversal, oversized/malformed file | Quarantine/reject and cleanup | High | No outside-root access or executable interpretation | 2/4 |

## Test fixtures and evidence

Fixtures should include minimal valid PaySim rows, forbidden internal fields,
malformed numeric values, boundary-length reviewer values, SQL metacharacters,
duplicate/partial step caches, altered checksums, symlink paths where supported,
and deterministic fake model objects. Each test records the input checksum,
result, exception class, side-effect file list, and sanitized diagnostics.

The Stage 2–5 tests remain the regression baseline. New security tests should
be additive and must not rewrite frozen artifacts. A Stage 6 validation run
must include the complete existing suite plus all security tests and a
before/after hash comparison for Modules 4–7.

## Research prototype versus production requirements

For this local prototype, safe schemas, checksums, read-only monitoring,
parameter binding, bounded fixtures, and explicit privacy assertions are
appropriate acceptance gates. Production additionally requires managed
identity, role-based authorization, key custody and signatures, protected
storage, network segmentation, secret management, centralized redacted audit
logs, dependency/SBOM governance, vulnerability response, rate limits, backup
and recovery, incident response, and independent penetration testing. Passing
local synthetic tests does not establish those controls.
