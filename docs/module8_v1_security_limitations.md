# Module 8 V1 Security Limitations

These limitations are accepted as research-prototype scope and are recorded
in the V1 freeze manifest.

| Risk | Severity | Classification | Required follow-up |
|---|---|---|---|
| No production authentication, signed sessions, or managed RBAC | High for production, not a supported-path bypass | Prototype limitation | Integrate an identity provider and request-boundary authorization before deployment |
| Development-only trusted-local context mechanism | Medium | Prototype limitation | Replace with verified principal-to-context adapter |
| Archived historical source snapshots remain directly executable if intentionally invoked | Medium | Historical reproducibility limitation | Restrict archival execution and publish only the secure launcher |
| Source-controlled checksum mapping assumes protected source provenance | High for hostile source environments | Trust-assumption limitation | Use authenticated manifests, signatures, and protected build provenance |
| Python joblib/pickle remains unsafe for inherently hostile objects | High for arbitrary inputs | Design limitation; arbitrary user artifacts rejected | Use isolated loading or safer model serialization for production |
| Dependency declarations use ranges and lack a complete lock/SBOM build | Medium | Supply-chain limitation | Produce locked, hashed environment and advisory review |
| Windows symlink negative test skipped on this host | Medium | Test coverage gap | Run the same test under a symlink-capable CI policy |
| Monitoring lifecycle path confinement is not a universal wrapper | Medium | Optional-wrapper limitation | Route all future publication paths through the trusted filesystem boundary |

No high-priority bypass remains on the documented supported launcher or trusted
model-loading paths. These limitations prevent a claim of production security,
but do not block the research-prototype V1 freeze.
