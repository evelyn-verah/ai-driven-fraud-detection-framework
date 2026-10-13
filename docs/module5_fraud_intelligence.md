# Module 5 Fraud Intelligence Version 1

Module 5 is frozen as `module5_v1_frozen` for the current research prototype. Its freeze manifest is [module5_v1_freeze_manifest.json](../artifacts/module5_authoritative_v1/module5_v1_freeze_manifest.json).

The frozen layer contains validated contracts, offline document ingestion, provenance-preserving knowledge-base publication, deterministic TF-IDF retrieval, domain-aware query normalization, evidence-grounded explanations, safety controls, and read-only integration with the frozen Module 4 risk engine. The authoritative knowledge base `module5_authoritative_v1` contains 10 curated summaries from verified government sources. Summaries are attributable research material and are not verbatim reproductions of the source publications.

Stage 6D compared the original retriever with the normalized retriever on the existing 31-case diagnostic fixture and a new 12-case development fixture. The revised metrics and per-case results are recorded in [stage6d_retrieval_comparison.json](../artifacts/module5_authoritative_v1/stage6d_retrieval_comparison.json). The suite passed 89 tests at freeze.

The current limitations are lexical vocabulary mismatch, partial misses in some multi-pattern top-three results, small diagnostic fixtures, simulated PaySim data, and the absence of production deployment evidence. Module 5 does not alter Module 4 scores, thresholds, models, caches, or holdout results.
