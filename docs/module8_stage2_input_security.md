# Module 8 Stage 2 — Input validation and secure data handling

Stage 2 adds a small validation boundary for the local prototype. It hardens
currently supported inputs without changing model features, scoring behavior,
frozen monitoring calculations, or the Module 4–7 artifact boundary.

## Actual input surfaces

The supported surfaces are:

- `src/ingestion/adapters.py`: local CSV path, dataset selector, bounded sample
  row count, and PaySim dataframe fields.
- `src/risk_engine/contracts.py`: internal transaction frames supplied by
  scoring/rules/state callers. Its existing contract remains unchanged; the new
  security helper can validate a stricter boundary before callers invoke it.
- `src/dashboard/feedback_store.py`: local row IDs, fixed review statuses,
  reviewer labels, and optional notes. Existing limits and parameterized SQL
  remain intact.
- `src/dashboard/data_access.py`: existing bounded page/filter values and
  holdout row IDs. These are already validated by Module 6 code.
- `src/monitoring/lifecycle.py`: versioned configuration and complete-step
  monitoring windows. The frozen Stage 5 implementation remains unchanged; the
  new helper validates mappings before an existing loader is called.

There is no upload endpoint, HTTP API, remote service, or network-facing file
receiver. Upload-specific controls remain planned rather than implemented.

## Centralized rules and limits

`src/security/input_validation.py` provides safe field-level errors and the
following contracts:

- Required PaySim model fields must exist; strict mode rejects unexpected
  fields. History keys and targets are opt-in.
- Transaction steps are finite, non-negative integers. Amounts are finite and
  non-negative. Other balance values must be finite but are not blanket-rejected
  when negative because the existing domain contract does not establish that
  every balance-like value is invalid.
- PaySim transaction types are restricted to `CASH_IN`, `CASH_OUT`, `DEBIT`,
  `PAYMENT`, and `TRANSFER`.
- Missing/null required values, NaN, infinity, invalid identifiers, unsupported
  encodings, and control characters are rejected.
- Text fields are bounded at 4,000 characters by default; identifiers are
  bounded to non-negative integers no larger than 10,000,000; paths are bounded
  to 4,096 characters.
- CSV inspection is bounded to 1,000,000 sampled rows and 2 GiB per input file.
  Full transaction validation permits up to 10,000,000 rows so legitimate
  PaySim research workloads are not constrained to the small inspection sample.
- Monitoring windows are restricted to the frozen holdout range 378–743 and at
  most 366 inclusive steps, matching the complete frozen range.
- Output-path validation requires a `.csv` filename and rejects control
  characters. It does not add an upload or network root because no such surface
  exists in the prototype.

The limits are resource safeguards for a 16 GB research laptop and are applied
before expensive parsing or model calls. They are not model thresholds.

## Threat IDs addressed

The changes directly address T03 (malformed transaction input), T05 (unsafe
path values at existing CSV/output boundaries), T08 (malformed monitoring
configuration), T10 (sensitive-safe validation errors), and T11 (bounded input
work). They add regression coverage for T02 privacy expectations and T06
frozen-artifact integrity. T01/T13 authentication, T06 signing, T07 safe model
deserialization, T09 tamper-evident reviews, T12 dependency provenance, and T14
uploads remain later-stage work.

## Tests performed

The new [test_module8_stage2_input_security.py](../tests/test_module8_stage2_input_security.py)
contains 19 tests covering valid frames and ingestion, missing fields, invalid
numeric values, NaN/infinity, negative and extreme amounts, supported and
unsupported types, unexpected fields, oversized strings, control characters,
invalid identifiers, malformed configurations, oversized windows, safe error
messages, bounded rows/paths, and frozen artifact hashes.

Focused security and adjacent regression tests passed **45 tests**. The full
project suite passed **160 tests**. A bounded synthetic end-to-end path validated
a PaySim frame, prepared the existing feature subset, and preserved the prior
output schema.

## Backward compatibility and remaining risks

Valid existing PaySim ingestion fixtures continue to work. No Module 4 model,
threshold, retrieval behavior, dashboard module, monitoring source, or frozen
artifact was modified. The new helpers are additive; strict validation is opt-in
for internal transaction callers, while existing ingestion now validates its
supported CSV path, sample bound, and PaySim frame before returning data.

Authentication/authorization, signed artifacts, unsafe deserialization,
filesystem confinement, tamper-evident review history, dependency locking and
SBOM review, centralized redacted logging, quotas across every dashboard path,
and upload quarantine remain open risks for later stages. Passing local
synthetic tests does not establish production security.
