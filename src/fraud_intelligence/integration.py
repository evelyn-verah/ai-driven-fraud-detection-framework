"""Read-only adapter and orchestration for Module 4 risk records."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import json
from typing import Any

from .contracts import GroundedExplanation, RetrievedEvidence, RiskAssessmentContext
from .explanations import generate_explanation
from .retrieval import RetrievalIndex, build_transaction_query


_REQUIRED = (
    "row_id", "step", "amount", "fraud_probability", "baseline_anomaly_intensity",
    "behavioral_anomaly_intensity", "rule_score_context", "alert", "transaction_type",
    "threshold", "threshold_provenance", "module4_architecture_version", "model_versions",
)


@dataclass(frozen=True)
class IntegratedRiskIntelligence:
    """Traceable output of the read-only Module 4 to Module 5 workflow."""

    context: RiskAssessmentContext
    query: str
    evidence: tuple[RetrievedEvidence, ...]
    explanation: GroundedExplanation


def _record_mapping(record: Any) -> dict[str, Any]:
    if isinstance(record, Mapping):
        return dict(record)
    if hasattr(record, "to_dict"):
        value = record.to_dict()
        if isinstance(value, Mapping):
            return dict(value)
    raise TypeError("Module 4 record must be a mapping or mapping-like record")


def _rules(value: Any) -> tuple[str, ...]:
    if value is None:
        raise ValueError("triggered_rules is required; do not infer rule context")
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValueError("triggered_rules string must contain JSON list data") from exc
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError("triggered_rules must be a sequence of strings")
    return tuple(value)


def adapt_module4_record(record: Any, *, transaction_metadata: Mapping[str, Any] | None = None) -> RiskAssessmentContext:
    """Map one existing Module 4 record without fabricating absent values.

    ``transaction_metadata`` is intended for the aligned input transaction row
    when a FinalRiskAssessment result contains only score columns. It is copied
    and never modified.
    """

    values = _record_mapping(record)
    if transaction_metadata is not None:
        supplied = dict(transaction_metadata)
        supplied.update(values)
        values = supplied
    aliases = {"transaction_type": "type", "rule_score_context": "rule_score", "module4_architecture_version": "architecture_version"}
    for target, source in aliases.items():
        if target not in values and source in values:
            values[target] = values[source]
    missing = [field for field in _REQUIRED if field not in values]
    if missing:
        raise ValueError(f"Module 4 record is missing required fields: {missing}")
    model_versions = values["model_versions"]
    if not isinstance(model_versions, Mapping) or not model_versions:
        raise ValueError("model_versions must be supplied as a non-empty mapping")
    behavioral = values.get("behavioral_features")
    if behavioral is not None and not isinstance(behavioral, Mapping):
        raise ValueError("behavioral_features must be a mapping when supplied")
    return RiskAssessmentContext(
        schema_version=values.get("schema_version", "module5_stage1_contracts_v1"),
        row_id=values["row_id"], step=values["step"], transaction_type=values["transaction_type"],
        amount=values["amount"], fraud_probability=values["fraud_probability"],
        baseline_anomaly_intensity=values["baseline_anomaly_intensity"],
        behavioral_anomaly_intensity=values["behavioral_anomaly_intensity"],
        rule_score_context=values["rule_score_context"], triggered_rules=_rules(values.get("triggered_rules")),
        alert=values["alert"], module4_architecture_version=values["module4_architecture_version"],
        threshold=values["threshold"], threshold_provenance=values["threshold_provenance"],
        model_versions=dict(model_versions), external_transaction_id=values.get("external_transaction_id"),
        behavioral_features=dict(behavioral) if behavioral is not None else None,
    )


def explain_module4_record(
    record: Any,
    retrieval_index: RetrievalIndex,
    *,
    transaction_metadata: Mapping[str, Any] | None = None,
    top_k: int = 5,
) -> IntegratedRiskIntelligence:
    """Run adapter → query → retrieval → explanation without scoring or mutation."""

    context = adapt_module4_record(record, transaction_metadata=transaction_metadata)
    query = build_transaction_query(context)
    evidence = retrieval_index.search(query, top_k=top_k)
    explanation = generate_explanation(context, evidence)
    return IntegratedRiskIntelligence(context=context, query=query, evidence=evidence, explanation=explanation)
