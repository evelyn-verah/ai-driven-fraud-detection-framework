# Next steps

1. Choose a licensed public fraud dataset with documented label definitions, timestamps, and preferably customer/entity identifiers. Consider the publicly described PaySim mobile money dataset for domain fit, but independently verify availability, provenance, licensing, and suitability before use. A credit-card fraud dataset is an alternative but does not automatically demonstrate mobile money transferability.
2. Implement dataset-specific loading and leakage-safe chronological train/validation/test splitting.
3. Record baseline PR-AUC, recall at fixed alert volume, calibration, and subgroup limitations.
4. Refine and validate the new leakage-safe behavioral anomaly-detection experiment, then build the integrated risk engine and a FastAPI scoring endpoint.
5. Add curated fraud knowledge base, retrieval and grounded explanations, analyst dashboard, feedback storage, and security testing.
6. Evaluate cross-dataset transfer only where feature/label semantics are compatible.
