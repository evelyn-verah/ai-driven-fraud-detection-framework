# Module 8 Stage 5 — Dependency and Supply-Chain Review

## Declared and observed environment

Direct declarations are in `requirements.txt`:

* NumPy `>=1.26,<3`
* pandas `>=2.0,<3`
* scikit-learn `>=1.4,<2`
* joblib `>=1.3,<2`
* pytest `>=8,<10`
* Streamlit `>=1.37,<2`
* pyarrow `>=25,<26`
* Altair `==5.5.0`

The configured Python 3.13.14 environment observed NumPy 2.5.1, pandas 2.3.3,
scikit-learn 1.9.1, joblib 1.6.0, pytest 9.1.1, Streamlit 1.37.0, pyarrow
25.0.0, and Altair 5.5.0. `python -m pip check` reported no broken
requirements.

Only Altair is exactly pinned. The other direct dependencies and transitive
packages are range-constrained or unpinned, so byte-for-byte environment
reproduction is not established. A local dependency inventory is recorded in
`artifacts/module8_stage5_dependency_inventory.json`; a machine-readable SBOM
can be generated locally from the same requirements and installed-package
inventory without adding a dependency.

## Risk assessment

The project uses joblib/pickle-based model artifacts, making trusted paths,
checksums, and provenance important. Stage 3 supplies an opt-in verification
wrapper, but legacy loaders bypass it. Dependency ranges can admit future
behavior changes. No reliable online vulnerability database or advisory scan
was available in this offline validation, so no CVE or vulnerability-free claim
is made. No external services were scanned and no dependencies were added.

## Recommendations

For a future release, generate a lock file and hashes in a controlled build,
record Python/platform provenance, review transitive licenses and advisories,
and route every model loader through authenticated artifact provenance. These
are production requirements outside the current frozen research prototype.
