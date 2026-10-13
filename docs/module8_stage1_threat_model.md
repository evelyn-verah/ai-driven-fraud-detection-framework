# Module 8 Stage 1 — Cybersecurity threat model

## Scope and method

This is an architecture and testing plan for the local research prototype. It
uses STRIDE categories (spoofing, tampering, repudiation, information
disclosure, denial of service, and elevation of privilege) against the actual
interfaces in Modules 1–7. No security control or production service is
implemented in Stage 1. PaySim is simulated; a threat here describes a
security failure, not evidence that the prototype has been attacked.

## Current architecture and trust boundaries

The dashboard in `src/dashboard/app.py` reads the validated Module 4 score
cache, the Module 6 metadata sidecar, and the Module 5 knowledge base. It
displays an allowlisted score projection and selected transaction metadata,
then writes analyst reviews to a separate SQLite database. The monitoring
package reads frozen scores, metadata, and the production-like feedback
database in read-only mode and writes versioned JSON reports. Ingestion and
risk-engine code validate PaySim frames and produce the frozen artifacts; the
model adapters consume already-loaded model objects. The repository has no
network API, login, role system, upload endpoint, or deployment identity
boundary.

Trust boundaries are:

1. A local operator or process to the Streamlit dashboard.
2. Dashboard code to frozen score, sidecar, and knowledge-base files.
3. Dashboard code to the mutable feedback SQLite file.
4. Monitoring code to frozen inputs and versioned output directories.
5. Ingestion/risk-engine callers to transaction frames and serialized model
   artifacts.
6. Repository source/dependency environment to the Python process.

## Assets

| Asset | Confidentiality | Integrity | Availability |
| --- | --- | --- | --- |
| Transaction amounts, balances, types, and stable row IDs | High | High | Medium |
| Frozen probabilities, alerts, anomaly intensities, threshold, and provenance | High | Critical | High |
| Internal alignment labels and raw account identifiers | Critical | High | Medium |
| Module 4–6 manifests, models, caches, and knowledge base | Medium/High | Critical | High |
| Analyst reviewer labels, notes, statuses, and review history | High | High | Medium |
| Monitoring reports and checksums | Medium | High | Medium |
| Source code, configuration, dependencies, and logs | Medium | Critical | Medium |

## Threat register

Severity is the consequence for this prototype if the precondition is met.
“Status” distinguishes a protection demonstrated by current tests from a
hypothetical risk that needs a future security test.

| ID / STRIDE | Asset and component | Attack scenario and preconditions | Current status | Proposed test and secure behavior | Severity | Recommended mitigation / acceptance |
| --- | --- | --- | --- | --- | --- | --- |
| T01 S/E | Dashboard and transaction data | A local or future remote caller reaches Streamlit without identity or role checks. | **Demonstrated gap:** no authentication or authorization code exists. | Start dashboard with an unauthenticated fixture request; secure behavior is deny-by-default and role-scoped access. | Critical | Add an external identity boundary and least-privilege roles before deployment; unauthenticated access must be rejected and every protected action audited. |
| T02 I/E | Analyst tables, details, monitoring JSON | An internal `isFraud`, `isFlaggedFraud`, account ID, reviewer, or note crosses an analyst-facing projection. | **Protection demonstrated:** allowlists and Stage 5 privacy checks exclude these fields; backend sidecars retain labels for alignment. | Serialize adversarial records and inspect every UI/report path; secure behavior is field absence, including nested values and errors. | High | Maintain explicit safe schemas and negative tests; acceptance requires zero forbidden fields in analyst/monitoring outputs. |
| T03 T/D | `src/ingestion/adapters.py`, risk contracts | Malformed, oversized, NaN, negative, unexpected-type, or label-bearing input reaches scoring. | **Partial protection demonstrated:** schema, null, binary-label, and negative-amount checks exist; no comprehensive byte/column/cardinality budget. | Fuzz synthetic CSV/dataframes and boundary sizes; reject malformed input before model calls with bounded work. | High | Add byte, row, column, dtype, and processing-time limits; acceptance requires deterministic rejection without partial publication. |
| T04 T | `feedback_store.py` SQLite writes/reads | A reviewer-controlled string attempts SQL injection or a malformed event corrupts review history. | **Protection demonstrated:** parameterized statements, fixed status choices, length checks, and SQLite constraints. | Insert quote/comment/Unicode payloads and malformed IDs; database schema and unrelated rows must remain intact. | High | Keep parameter binding and add authorizer/transaction/concurrency tests; acceptance requires no statement expansion and atomic writes. |
| T05 T/E | Config, output, raw/cache paths | A path or run ID uses `..`, a symlink, UNC path, or another user-controlled location to read or overwrite files. | **Partial protection:** run IDs reject path separators and completed run IDs are immutable; configured paths are not confined to an approved root. | Use traversal, symlink, existing-file, and directory substitution fixtures; reject escapes and never overwrite frozen or completed files. | High | Canonicalize and constrain roots, reject symlinks where appropriate, and use atomic no-clobber publication. Acceptance requires all resolved paths stay in approved roots. |
| T06 T | Frozen score/model/KB artifacts | A writable artifact, sidecar, or manifest is replaced with altered scores or knowledge-base content. | **Protection demonstrated:** SHA-256 and schema/provenance checks exist for score, sidecar, and KB; no signature or protected storage. | Change one byte, swap a manifest, or mismatch versions; loading must fail closed before use. | Critical | Sign manifests, use read-only ownership/ACLs, and verify hashes immediately before use. Acceptance requires tampering detection and no scoring/publication. |
| T07 T/E | `joblib`/model loading and model adapters | A hostile serialized model executes code during deserialization or returns invalid scores. | **Hypothetical risk:** current source uses trusted model objects/adapters; the reviewed path does not establish a safe deserialization boundary. | Supply a synthetic hostile or invalid artifact in an isolated process; secure behavior is refusal without executing application privileges. | Critical | Do not deserialize untrusted files; use signed, approved formats or isolated loaders. Acceptance requires provenance verification before load and bounded score validation after load. |
| T08 T/E | JSON configuration and versioned manifests | A config changes threshold, model version, source paths, output root, or schema to bypass controls. | **Partial protection:** Stage 5 validates model version, threshold, windows, and paths for existence; no signature or immutable policy source. | Mutate each security-sensitive field and use duplicate/unknown keys; reject mismatches before input reads. | High | Sign/allowlist configuration, reject unknown fields, and separate operator policy from run parameters. Acceptance requires unchanged approved threshold/model identity. |
| T09 T/R | Analyst review database | A local process edits/deletes reviews, impersonates a reviewer, or changes timestamps. | **Demonstrated gap:** SQLite is local and append-only by convention; no authenticated author, ACL, audit chain, or tamper-evident journal. | Modify/delete rows and replay events in a fixture; secure behavior detects or rejects unauthorized changes and preserves an audit trail. | High | Use OS/database ACLs, authenticated principals, append-only audit records, and integrity snapshots. Acceptance requires unauthorized mutation detection and attributable events. |
| T10 I/R | Logs, exceptions, monitoring artifacts | Errors or debug output include labels, account identifiers, reviewer identity, notes, paths, or sensitive payloads. | **Partial protection:** monitoring outputs are label-free and dashboard projections are allowlisted; no centralized log redaction policy is present. | Trigger validation failures with sensitive fixture values and scan logs/errors/artifacts. Secure behavior emits bounded identifiers and no sensitive fields. | High | Define structured redacted logging and retention; acceptance requires forbidden-field scans pass for success and failure paths. |
| T11 D | CSV readers, Parquet/JSON loaders, Streamlit filters | Huge files, pathological rows, many steps, giant notes, or repeated requests exhaust memory/CPU/disk. | **Partial protection:** bounded ingestion samples, page-size and note limits exist; several loaders process trusted full artifacts. | Generate size/cardinality/decompression and repeated-request fixtures; secure behavior rejects or caps work before exhaustion. | High | Set byte/row/time/memory budgets, pagination, quotas, and output limits. Acceptance requires bounded resource use and no partial artifact. |
| T12 T/E | Python dependencies and build environment | A compromised or vulnerable package changes model, parsing, or dashboard behavior. | **Hypothetical risk:** `requirements.txt` is present; no lock/SBOM/signature or automated dependency policy is part of Module 8. | Reproduce an offline dependency inventory and audit pinned versions/checksums; fail on disallowed or unpinned packages. | High | Lock and hash dependencies, review advisories, generate an SBOM, and isolate build/runtime environments. Acceptance requires reproducible installation and documented exceptions. |
| T13 S/E | All dashboard write/read actions | A user performs review writes or reads sensitive details outside their role. | **Demonstrated gap:** local Streamlit has no identity, authorization, CSRF/session policy, or action audit. | Simulate roles and direct function calls; secure behavior denies unauthorized reads/writes and records actor/action. | Critical | Add authentication, authorization, CSRF/session controls, and audit events at the deployment boundary. Acceptance requires a negative matrix for every protected action. |
| T14 T/D | Ingestion CLI and future file inputs | An uploaded or operator-supplied file is a symlink, polyglot, malformed CSV, or unexpected format that escapes the intended workflow. | **Not supported today:** no dashboard upload endpoint; CLI accepts a filesystem path and reads CSV. | Synthetic upload/path fixtures must test type sniffing, symlinks, traversal, size, and cleanup. Secure behavior is reject/quarantine with no execution or overwrite. | High | Keep uploads out of the prototype until a quarantine pipeline exists; use content validation, isolated staging, and safe cleanup. Acceptance requires no outside-root access and no executable interpretation. |

## Highest-priority risks

T01/T13 (missing identity and authorization), T06/T07 (artifact tampering and
unsafe deserialization), and T05/T08 (path/config trust) are the first risks to
address before any network or multi-user deployment. T02 is a high-value
regression area because internal labels are intentionally present in alignment
sidecars even though analyst projections currently exclude them. T03/T11 cover
the practical denial-of-service risk on a 16 GB research laptop.

## Demonstrated protections versus open hypotheses

Current tests demonstrate schema and threshold validation, sidecar/score
alignment, parameterized SQLite access, note/status bounds, analyst-safe score
projections, knowledge-base checksums, and Module 7 output privacy. They do not
demonstrate authentication, authorization, secure deserialization, signed
artifacts, path confinement, resource quotas, tamper-evident review history,
dependency provenance, or upload safety. Those remain testable hypotheses for
later stages.

Stage 1 changes documentation only. Frozen Modules 4–7 and their manifests are
not modified.
