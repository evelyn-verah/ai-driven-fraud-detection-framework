"""Validated, deterministic contracts for Module 5.

These structures carry Module 4 values and external evidence without changing
the frozen risk engine. Retrieved text is data only; it is never executable.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
from datetime import date
import hashlib
import json
import math
import re
from types import MappingProxyType
from typing import Any, Mapping
from urllib.parse import urlparse


CONTRACT_SCHEMA_VERSION = "module5_stage1_contracts_v1"
_SHA256 = re.compile(r"^[0-9a-fA-F]{64}$")
_SOURCE_TYPES = {"authoritative", "research", "illustrative_synthetic"}
_SCORE_FIELDS = (
    "amount", "fraud_probability", "baseline_anomaly_intensity",
    "behavioral_anomaly_intensity", "rule_score_context", "threshold",
)


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value


def _finite(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise ValueError(f"{field} must be a finite number")
    return value


def _url(value: Any, field: str, *, allow_synthetic: bool = False) -> str:
    value = _text(value, field)
    parsed = urlparse(value)
    allowed = {"https", "http"} | ({"synthetic"} if allow_synthetic else set())
    if parsed.scheme not in allowed or (parsed.scheme != "synthetic" and not parsed.netloc):
        raise ValueError(f"{field} must be an absolute HTTP(S) URL")
    return value


def _tuple_strings(values: Any, field: str) -> tuple[str, ...]:
    if values is None:
        return ()
    if isinstance(values, (str, bytes)):
        raise ValueError(f"{field} must be a sequence of strings")
    result = tuple(_text(value, field) for value in values)
    return result


def _mapping(values: Mapping[str, Any] | None, field: str) -> Mapping[str, Any] | None:
    if values is None:
        return None
    if not isinstance(values, Mapping):
        raise ValueError(f"{field} must be a mapping")
    copied = {}
    for key, value in values.items():
        key = _text(key, f"{field} key")
        copied[key] = _finite(value, f"{field}.{key}")
    return MappingProxyType(copied)


def _jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return _jsonable(asdict(value))
    if isinstance(value, Mapping):
        return {key: _jsonable(value[key]) for key in sorted(value)}
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    if isinstance(value, (date,)):
        return value.isoformat()
    return value


class _Serializable:
    def to_dict(self) -> dict[str, Any]:
        return _jsonable(self.__dict__)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=False)


@dataclass(frozen=True)
class RiskAssessmentContext(_Serializable):
    schema_version: str
    row_id: int
    step: int
    transaction_type: str
    amount: float
    fraud_probability: float
    baseline_anomaly_intensity: float
    behavioral_anomaly_intensity: float
    rule_score_context: float
    triggered_rules: tuple[str, ...]
    alert: bool
    module4_architecture_version: str
    threshold: float
    threshold_provenance: str
    model_versions: Mapping[str, str]
    external_transaction_id: str | None = None
    behavioral_features: Mapping[str, float] | None = None

    def __post_init__(self) -> None:
        if self.schema_version != CONTRACT_SCHEMA_VERSION:
            raise ValueError("unsupported contract schema version")
        if not isinstance(self.row_id, int) or isinstance(self.row_id, bool) or self.row_id < 0:
            raise ValueError("row_id must be a non-negative integer")
        if not isinstance(self.step, int) or isinstance(self.step, bool) or self.step < 0:
            raise ValueError("step must be a non-negative integer")
        _text(self.transaction_type, "transaction_type")
        for field in _SCORE_FIELDS:
            _finite(getattr(self, field), field)
        if not isinstance(self.alert, bool):
            raise ValueError("alert must be boolean")
        if self.external_transaction_id is not None:
            _text(self.external_transaction_id, "external_transaction_id")
        _text(self.module4_architecture_version, "module4_architecture_version")
        _text(self.threshold_provenance, "threshold_provenance")
        rules = _tuple_strings(self.triggered_rules, "triggered_rules")
        object.__setattr__(self, "triggered_rules", rules)
        if not isinstance(self.model_versions, Mapping) or not self.model_versions:
            raise ValueError("model_versions must be a non-empty mapping")
        for key, value in self.model_versions.items():
            _text(key, "model_versions key"); _text(value, "model_versions value")
        features = _mapping(self.behavioral_features, "behavioral_features")
        object.__setattr__(self, "behavioral_features", features)


@dataclass(frozen=True)
class FraudIntelligenceDocument(_Serializable):
    document_id: str
    title: str
    category: str
    description: str
    behavioral_indicators: tuple[str, ...]
    investigative_considerations: tuple[str, ...]
    source_organization: str
    source_url: str
    source_type: str
    publication_or_access_date: str
    document_version: str
    content: str
    content_checksum: str
    knowledge_base_version: str

    def __post_init__(self) -> None:
        for field in ("document_id", "title", "category", "description", "source_organization", "publication_or_access_date", "document_version", "content", "knowledge_base_version"):
            _text(getattr(self, field), field)
        if self.source_type not in _SOURCE_TYPES:
            raise ValueError("unsupported source_type")
        _url(self.source_url, "source_url", allow_synthetic=self.source_type == "illustrative_synthetic")
        if not _SHA256.fullmatch(self.content_checksum) or hashlib.sha256(self.content.encode("utf-8")).hexdigest() != self.content_checksum.lower():
            raise ValueError("content_checksum does not match UTF-8 content")
        object.__setattr__(self, "behavioral_indicators", _tuple_strings(self.behavioral_indicators, "behavioral_indicators"))
        object.__setattr__(self, "investigative_considerations", _tuple_strings(self.investigative_considerations, "investigative_considerations"))


@dataclass(frozen=True)
class RetrievedEvidence(_Serializable):
    document_id: str
    chunk_id: str
    passage: str
    source_organization: str
    source_url: str
    source_type: str
    retrieval_score: float
    knowledge_base_version: str

    def __post_init__(self) -> None:
        for field in ("document_id", "chunk_id", "passage", "source_organization", "knowledge_base_version"):
            _text(getattr(self, field), field)
        _url(self.source_url, "source_url", allow_synthetic=self.source_type == "illustrative_synthetic")
        if self.source_type not in _SOURCE_TYPES:
            raise ValueError("unsupported source_type")
        _finite(self.retrieval_score, "retrieval_score")


@dataclass(frozen=True)
class GroundedExplanation(_Serializable):
    transaction_key: int
    observed_facts: tuple[str, ...]
    model_indicators: tuple[str, ...]
    retrieved_evidence: tuple[RetrievedEvidence, ...]
    possible_interpretations: tuple[str, ...]
    uncertainty_and_limitations: tuple[str, ...]
    suggested_review_steps: tuple[str, ...]
    citations: tuple[str, ...]
    generator_version: str

    def __post_init__(self) -> None:
        if not isinstance(self.transaction_key, int) or self.transaction_key < 0:
            raise ValueError("transaction_key must be a non-negative integer")
        for field in ("observed_facts", "model_indicators", "possible_interpretations", "uncertainty_and_limitations", "suggested_review_steps", "citations"):
            object.__setattr__(self, field, _tuple_strings(getattr(self, field), field))
        if not isinstance(self.retrieved_evidence, tuple) or any(not isinstance(item, RetrievedEvidence) for item in self.retrieved_evidence):
            raise ValueError("retrieved_evidence must contain RetrievedEvidence")
        allowed_citations = {item.document_id for item in self.retrieved_evidence} | {item.source_url for item in self.retrieved_evidence}
        if any(citation not in allowed_citations for citation in self.citations):
            raise ValueError("unsupported citation")
        _text(self.generator_version, "generator_version")


def validate_document_set(documents: tuple[FraudIntelligenceDocument, ...] | list[FraudIntelligenceDocument]) -> tuple[FraudIntelligenceDocument, ...]:
    """Validate a knowledge-base document collection and reject duplicate IDs."""

    result = tuple(documents)
    if any(not isinstance(document, FraudIntelligenceDocument) for document in result):
        raise ValueError("document set contains an invalid document")
    identifiers = [document.document_id for document in result]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("duplicate document identifiers")
    return result
