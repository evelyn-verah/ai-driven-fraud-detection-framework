"""Deterministic, local-first retrieval over a validated Module 5 knowledge base."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import hashlib
import json
import math
import re
from typing import Any, Iterable

from sklearn.feature_extraction.text import TfidfVectorizer

from .contracts import FraudIntelligenceDocument, RetrievedEvidence, RiskAssessmentContext
from .ingestion import normalize_text
from .knowledge_base import KNOWLEDGE_BASE_SCHEMA_VERSION, KnowledgeBaseChunk


DEFAULT_SCORE_CUTOFF = 0.05

# Query normalization is deliberately small and deterministic.  It maps common
# investigator phrasing to terms present in the curated corpus; it does not
# change document text, scores, or the retrieval cutoff.
_QUERY_ALIASES: dict[str, tuple[str, ...]] = {
    "unusual": ("suspicious",),
    "incoming": ("receive",),
    "outgoing": ("transfer",),
    "counterparties": ("account",),
    "counterparty": ("account",),
    "sequence": ("money", "mule"),
    "credentials": ("credential",),
    "logins": ("login",),
    "payments": ("payment",),
    "spearphishing": ("phishing",),
    "phone": ("sim",),
    "number": ("sim",),
    "takeover": ("account",),
    "forwarded": ("forwarding",),
    "calls": ("call",),
}
_MEANINGFUL_QUERY_TERMS = {
    "account", "access", "attachment", "bec", "compromise", "credential",
    "email", "fraud", "funds", "impersonation", "illicit", "login", "money",
    "mule", "phishing", "payment", "pin", "scam", "simswap", "social",
    "suspicious", "transfer", "verification", "password", "otp", "mfa", "phishing",
    "sms", "call", "forwarding", "sim", "collaboration", "lure", "rapid", "movement",
    "recipient", "recipients", "receive",
}


def normalize_query(query: str) -> str:
    """Normalize investigator wording without inventing transaction facts.

    Unknown and generic-only queries are rejected before vectorization.  A
    query mentioning incoming/outgoing counterparties or a sequence of funds
    receives the indexed ``money mule`` and ``red flags`` vocabulary so that
    the two curated transfer-pattern documents can be found despite lexical
    mismatch.  This is a retrieval aid, never a fraud conclusion.
    """
    if not isinstance(query, str):
        raise ValueError("query must be a string")
    tokens = re.findall(r"(?u)\b\w+\b", query.lower())
    expanded: list[str] = []
    for token in tokens:
        expanded.extend(_QUERY_ALIASES.get(token, (token,)))
    if {"incoming", "outgoing", "counterparties", "counterparty", "sequence"}.intersection(tokens):
        expanded.extend(("money", "mule", "red", "flags"))
    meaningful = [token for token in expanded if token in _MEANINGFUL_QUERY_TERMS]
    if not meaningful:
        return ""
    return " ".join(expanded)


def _sha256_bytes(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"{path.name} must contain JSON objects")
            records.append(value)
    return records


def _validate_knowledge_base(path: str | Path, expected_version: str | None) -> tuple[dict[str, Any], tuple[FraudIntelligenceDocument, ...], tuple[KnowledgeBaseChunk, ...]]:
    root = Path(path)
    manifest_path, documents_path, chunks_path = root / "manifest.json", root / "documents.jsonl", root / "chunks.jsonl"
    if not root.is_dir() or not all(item.is_file() for item in (manifest_path, documents_path, chunks_path)):
        raise ValueError("knowledge base is missing required files")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid knowledge-base manifest: {exc}") from exc
    if manifest.get("schema_version") != KNOWLEDGE_BASE_SCHEMA_VERSION or manifest.get("validation_status") != "passed":
        raise ValueError("unsupported or unvalidated knowledge-base manifest")
    version = manifest.get("knowledge_base_version")
    if not isinstance(version, str) or (expected_version is not None and version != expected_version):
        raise ValueError("knowledge-base version mismatch")
    checksums = manifest.get("checksums")
    if not isinstance(checksums, dict) or _sha256_bytes(documents_path) != checksums.get("documents_sha256") or _sha256_bytes(chunks_path) != checksums.get("chunks_sha256"):
        raise ValueError("knowledge-base file checksum mismatch")
    try:
        documents = tuple(FraudIntelligenceDocument(**record) for record in _load_jsonl(documents_path))
        chunks = tuple(KnowledgeBaseChunk(**record) for record in _load_jsonl(chunks_path))
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid knowledge-base records: {exc}") from exc
    document_ids = [document.document_id for document in documents]
    chunk_ids = [chunk.chunk_id for chunk in chunks]
    if len(document_ids) != len(set(document_ids)) or document_ids != manifest.get("document_ids"):
        raise ValueError("document identifiers do not match manifest")
    if len(chunk_ids) != len(set(chunk_ids)) or chunk_ids != manifest.get("chunk_ids"):
        raise ValueError("chunk identifiers do not match manifest")
    if len(documents) != manifest.get("document_count") or len(chunks) != manifest.get("chunk_count"):
        raise ValueError("knowledge-base counts do not match manifest")
    by_id = {document.document_id: document for document in documents}
    for chunk in chunks:
        document = by_id.get(chunk.document_id)
        if document is None or chunk.knowledge_base_version != version:
            raise ValueError("chunk-to-document relationship is invalid")
        normalized = normalize_text(document.content)
        if not (0 <= chunk.start_offset < chunk.end_offset <= len(normalized)) or chunk.passage != normalized[chunk.start_offset:chunk.end_offset]:
            raise ValueError("chunk passage or offsets are invalid")
        expected_chunk_id = hashlib.sha256(f"{chunk.document_id}:{chunk.start_offset}:{chunk.end_offset}:{chunk.passage}".encode("utf-8")).hexdigest()[:24]
        if chunk.chunk_id != expected_chunk_id or chunk.source_type != document.source_type or chunk.source_url != document.source_url:
            raise ValueError("chunk provenance or identifier is invalid")
        try:
            RetrievedEvidence(document_id=chunk.document_id, chunk_id=chunk.chunk_id, passage=chunk.passage, source_organization=chunk.source_organization, source_url=chunk.source_url, source_type=chunk.source_type, retrieval_score=0.0, knowledge_base_version=chunk.knowledge_base_version)
        except ValueError as exc:
            raise ValueError(f"chunk provenance is invalid: {exc}") from exc
    summary: dict[str, int] = {}
    for document in documents:
        summary[document.source_type] = summary.get(document.source_type, 0) + 1
    if summary != manifest.get("source_provenance_summary"):
        raise ValueError("source provenance summary does not match records")
    return manifest, documents, chunks


@dataclass(frozen=True)
class RetrievalIndex:
    knowledge_base_version: str
    vectorizer: TfidfVectorizer
    matrix: Any
    chunks: tuple[KnowledgeBaseChunk, ...]
    documents: dict[str, FraudIntelligenceDocument]
    score_cutoff: float = DEFAULT_SCORE_CUTOFF

    def search(self, query: str, *, top_k: int = 5, source_type: str | None = None, category: str | None = None) -> tuple[RetrievedEvidence, ...]:
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query must be a non-empty string")
        if not isinstance(top_k, int) or isinstance(top_k, bool) or top_k < 1:
            raise ValueError("top_k must be a positive integer")
        if source_type is not None and source_type not in {"authoritative", "research", "illustrative_synthetic"}:
            raise ValueError("unsupported source_type filter")
        if category is not None and (not isinstance(category, str) or not category.strip()):
            raise ValueError("category filter must be a non-empty string")
        normalized_query = normalize_query(query)
        if not normalized_query:
            # Preserve the documented zero-cutoff tie behavior used for
            # deterministic diagnostics; normal searches reject generic-only
            # queries before scoring.
            if self.score_cutoff > 0:
                return ()
            normalized_query = query
        scores = (self.vectorizer.transform([normalized_query]) @ self.matrix.T).toarray()[0]
        candidates: list[tuple[float, KnowledgeBaseChunk]] = []
        for score, chunk in zip(scores, self.chunks):
            document = self.documents[chunk.document_id]
            if source_type is not None and document.source_type != source_type:
                continue
            if category is not None and document.category != category:
                continue
            score = float(score)
            if not math.isfinite(score) or score < self.score_cutoff:
                continue
            candidates.append((score, chunk))
        candidates.sort(key=lambda item: (-item[0], item[1].document_id, item[1].chunk_id))
        return tuple(RetrievedEvidence(document_id=chunk.document_id, chunk_id=chunk.chunk_id, passage=chunk.passage, source_organization=chunk.source_organization, source_url=chunk.source_url, source_type=chunk.source_type, retrieval_score=score, knowledge_base_version=self.knowledge_base_version) for score, chunk in candidates[:top_k])


def build_retrieval_index(knowledge_base_dir: str | Path, *, expected_version: str | None = None, score_cutoff: float = DEFAULT_SCORE_CUTOFF) -> RetrievalIndex:
    if not isinstance(score_cutoff, (int, float)) or isinstance(score_cutoff, bool) or not math.isfinite(float(score_cutoff)) or not 0 <= score_cutoff <= 1:
        raise ValueError("score_cutoff must be finite and between 0 and 1")
    manifest, documents, chunks = _validate_knowledge_base(knowledge_base_dir, expected_version)
    vectorizer = TfidfVectorizer(lowercase=True, norm="l2", smooth_idf=True, sublinear_tf=False, token_pattern=r"(?u)\b\w+\b")
    matrix = vectorizer.fit_transform([chunk.passage for chunk in chunks])
    return RetrievalIndex(manifest["knowledge_base_version"], vectorizer, matrix, chunks, {document.document_id: document for document in documents}, float(score_cutoff))


def build_transaction_query(context: RiskAssessmentContext) -> str:
    """Build a deterministic query from supplied Module 4 context only."""

    if not isinstance(context, RiskAssessmentContext):
        raise TypeError("context must be RiskAssessmentContext")
    parts = [f"transaction_type {context.transaction_type}"]
    if context.triggered_rules:
        parts.append("rules " + " ".join(context.triggered_rules))
    if context.behavioral_features:
        parts.append("behavioral_features " + " ".join(f"{key} {value:g}" for key, value in sorted(context.behavioral_features.items())))
    if context.baseline_anomaly_intensity:
        parts.append("baseline_anomaly_indicator")
    if context.behavioral_anomaly_intensity:
        parts.append("behavioral_anomaly_indicator")
    return " ".join(parts)


def evaluate_retrieval(index: RetrievalIndex, cases: Iterable[dict[str, Any]], *, top_k: int = 3) -> dict[str, float | int]:
    """Evaluate a small labeled fixture; this is not a holdout metric."""

    cases = tuple(cases)
    relevant_cases = [case for case in cases if case.get("expected_document_ids")]
    recall = precision = reciprocal = 0.0
    for case in relevant_cases:
        results = index.search(case["query"], top_k=top_k)
        ids = [result.document_id for result in results]
        expected = set(case["expected_document_ids"])
        hits = len(expected.intersection(ids))
        recall += hits / len(expected)
        precision += hits / top_k
        reciprocal += next((1 / (position + 1) for position, identifier in enumerate(ids) if identifier in expected), 0.0)
    no_evidence_cases = [case for case in cases if case.get("expected_document_ids") == []]
    rejected = sum(not index.search(case["query"], top_k=top_k) for case in no_evidence_cases)
    return {"case_count": len(cases), "recall_at_k": recall / len(relevant_cases) if relevant_cases else 0.0, "precision_at_k": precision / len(relevant_cases) if relevant_cases else 0.0, "mean_reciprocal_rank": reciprocal / len(relevant_cases) if relevant_cases else 0.0, "no_evidence_rejection_accuracy": rejected / len(no_evidence_cases) if no_evidence_cases else 0.0}
