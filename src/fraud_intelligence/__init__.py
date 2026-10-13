"""Stage 1 contracts for the fraud-intelligence layer."""

from .contracts import (
    CONTRACT_SCHEMA_VERSION,
    FraudIntelligenceDocument,
    GroundedExplanation,
    RetrievedEvidence,
    RiskAssessmentContext,
    validate_document_set,
)
from .ingestion import load_documents, normalize_text
from .knowledge_base import KNOWLEDGE_BASE_SCHEMA_VERSION, KnowledgeBaseChunk, build_knowledge_base, chunk_document
from .retrieval import RetrievalIndex, build_retrieval_index, build_transaction_query, evaluate_retrieval, normalize_query
from .explanations import EXPLANATION_GENERATOR_VERSION, generate_explanation
from .safety import contains_prompt_injection, evidence_has_conflict, redact_sensitive_identifiers
from .integration import IntegratedRiskIntelligence, adapt_module4_record, explain_module4_record

__all__ = [
    "CONTRACT_SCHEMA_VERSION",
    "FraudIntelligenceDocument",
    "GroundedExplanation",
    "RetrievedEvidence",
    "RiskAssessmentContext",
    "validate_document_set",
    "KNOWLEDGE_BASE_SCHEMA_VERSION",
    "KnowledgeBaseChunk",
    "build_knowledge_base",
    "chunk_document",
    "load_documents",
    "normalize_text",
    "RetrievalIndex",
    "build_retrieval_index",
    "build_transaction_query",
    "evaluate_retrieval",
    "normalize_query",
    "EXPLANATION_GENERATOR_VERSION",
    "generate_explanation",
    "contains_prompt_injection",
    "evidence_has_conflict",
    "redact_sensitive_identifiers",
    "IntegratedRiskIntelligence",
    "adapt_module4_record",
    "explain_module4_record",
]
