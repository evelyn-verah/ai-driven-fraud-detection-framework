# Module 8 Stage 4 — Dashboard Access Controls and Sensitive-Data Protection

Stage 4 adds a separate access-control and projection facade in
`src/security/dashboard_access.py`. Frozen Module 6 dashboard code and Module
7 monitoring code remain unchanged.

## Research-prototype authorization contract

The facade is deny-by-default and supports three local prototype roles:

| Role | Permissions |
| --- | --- |
| Viewer | Read dashboard score projections and transaction details. |
| Analyst | Viewer permissions plus review submission and aggregate feedback reads. |
| Administrator | Viewer permissions plus diagnostic reads and aggregate feedback reads. |

Only `issue_local_context(..., trusted_local_identity=True)` can issue a
context accepted by `require_permission`. The marker represents an out-of-band
local configuration decision for tests or a controlled local launch; it is not
authentication, enterprise identity, managed RBAC, or a production security
boundary. A role string supplied by an untrusted caller, a missing context, an
unknown role, or a manually constructed context is denied.

## Enforcement points

* `authorized_scores` checks `dashboard.read` before projecting score data.
* `authorized_detail` checks `transaction.detail` before detail rendering.
* `submit_review` checks `review.submit` before invoking the Stage 3 validated
  SQLite writer.
* `safe_feedback_summary` checks `feedback.read` and returns only event and
  status counts; reviewer labels and notes never cross this boundary.
* Unknown operations and roles fail closed through `require_permission`.

## Sensitive-data contract

Analyst-facing score projections allow only row ID, step, probability, anomaly
context, rule-score context, and alert. Transaction detail projections allow
the selected row's non-identity transaction facts and bounded model/explanation
context. They exclude `isFraud`, `isFlaggedFraud`, `nameOrig`, `nameDest`,
reviewer identities, notes, training labels, and verified-fraud outcomes.
Analyst feedback remains mutable workflow information and is not a fraud label.
No export or download endpoint exists in this local Streamlit prototype.

## Tests and threat mapping

`tests/test_module8_stage4_dashboard_security.py` contains seven synthetic
tests covering viewer reads and write denial, analyst review access, unknown and
missing contexts, privilege escalation, safe detail schemas, administrator
scope, and frozen artifact checksums. It addresses T01, T02, T03, T09, T10,
T12, T13, and T14. Stage 2/3 input, storage, and privacy boundaries remain
composable with this facade.

Focused Stage 4 tests: **7 passed**. The final full-suite result is recorded in
the implementation status document.

## Limitations

Streamlit itself still has no real authentication, session signing, CSRF
protection, deployment identity, or network authorization. The existing frozen
dashboard directly renders review details when its `main` function is used;
the facade provides the safe integration boundary without changing that frozen
file. Production deployment must integrate a real identity provider and enforce
authorization at the request/session boundary before exposing the dashboard.
