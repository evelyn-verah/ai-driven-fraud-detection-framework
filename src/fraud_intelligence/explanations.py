"""Deterministic evidence-grounded explanations for Module 4 risk outputs."""

from __future__ import annotations

from collections.abc import Iterable

from .contracts import GroundedExplanation, RetrievedEvidence, RiskAssessmentContext
from .safety import contains_prompt_injection, evidence_has_conflict, redact_sensitive_identifiers


EXPLANATION_GENERATOR_VERSION = "module5_stage4_deterministic_v1"


def _number(value: float) -> str:
    """Use Python's stable representation without changing the structured value."""

    return repr(value)


def generate_explanation(
    context: RiskAssessmentContext,
    evidence: Iterable[RetrievedEvidence],
    *,
    generator_version: str = EXPLANATION_GENERATOR_VERSION,
) -> GroundedExplanation:
    """Create a validated explanation without altering Module 4 decisions."""

    if not isinstance(context, RiskAssessmentContext):
        raise TypeError("context must be RiskAssessmentContext")
    evidence_tuple = tuple(evidence)
    if any(not isinstance(item, RetrievedEvidence) for item in evidence_tuple):
        raise TypeError("evidence must contain RetrievedEvidence records")

    observed = [
        redact_sensitive_identifiers(f"Transaction type observed: {context.transaction_type}."),
        redact_sensitive_identifiers(f"Transaction amount observed: {_number(context.amount)}."),
        f"Simulation step observed: {context.step}.",
    ]
    if context.external_transaction_id is not None:
        observed.append("External transaction identifier withheld from generated prose for privacy.")
    if context.behavioral_features is not None:
        observed.append(f"Behavioral features supplied: {', '.join(sorted(context.behavioral_features))}.")
    else:
        observed.append("No optional behavioral features were supplied.")

    rules = ", ".join(context.triggered_rules) if context.triggered_rules else "none supplied"
    model_indicators = (
        f"Fraud probability supplied by Module 4: {_number(context.fraud_probability)}.",
        f"Frozen alert threshold: {_number(context.threshold)}.",
        f"Alert decision supplied by Module 4: {context.alert}.",
        f"Baseline anomaly intensity: {_number(context.baseline_anomaly_intensity)}.",
        f"Behavioral anomaly intensity: {_number(context.behavioral_anomaly_intensity)}.",
        f"Triggered rules: {rules}.",
        f"Rule score context: {_number(context.rule_score_context)}.",
        "No individual Random Forest feature contribution or causal explanation was inferred.",
    )

    interpretations: list[str] = []
    limitations: list[str] = []
    citations: list[str] = []
    injection_seen = False
    for item in evidence_tuple:
        citations.append(item.document_id)
        source_label = "illustrative synthetic" if item.source_type == "illustrative_synthetic" else item.source_type
        article = "an" if source_label[0].lower() in "aeiou" else "a"
        interpretations.append(
            f"Passage {item.document_id} ({item.source_url}) describes {article} {source_label} fraud pattern that may be relevant to review; retrieval similarity is not proof of fraud."
        )
        if item.source_type == "illustrative_synthetic":
            limitations.append(f"{item.document_id} is illustrative synthetic intelligence, not verified external evidence.")
        if contains_prompt_injection(item.passage):
            injection_seen = True
    if not evidence_tuple:
        limitations.extend(("No retrieved fraud-intelligence evidence met the relevance cutoff.", "This explanation relies on Module 4 indicators and observed transaction facts only."))
        interpretations.append("No external fraud pattern was identified for this transaction context.")
    else:
        limitations.append("Retrieved passages provide general context and do not establish that this transaction is fraudulent.")
        if evidence_has_conflict(item.passage for item in evidence_tuple):
            limitations.append("Retrieved passages contain potentially conflicting language; an investigator should resolve the conflict against source material.")
    if injection_seen:
        limitations.append("Embedded instructions in retrieved text were treated as inert untrusted content and ignored.")
    limitations.append("This component does not establish live financial-system deployment or a regulatory conclusion.")

    review = [
        "Review the transaction sequence and counterparties using approved investigative records.",
        "Confirm relevant account-holder or payment-request details through a trusted channel.",
        "Use the retrieved passages as context and retain the cited source for audit; do not take irreversible action from this explanation alone.",
    ]
    return GroundedExplanation(
        transaction_key=context.row_id,
        observed_facts=tuple(observed),
        model_indicators=model_indicators,
        retrieved_evidence=evidence_tuple,
        possible_interpretations=tuple(interpretations),
        uncertainty_and_limitations=tuple(limitations),
        suggested_review_steps=tuple(review),
        citations=tuple(citations),
        generator_version=generator_version,
    )
