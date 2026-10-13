"""Small, deterministic safety helpers for evidence-grounded explanations."""

from __future__ import annotations

import re
from collections.abc import Iterable


_INSTRUCTION_MARKERS = re.compile(
    r"\b(ignore|disregard|follow|system prompt|developer message|execute|reveal|override)\b",
    re.IGNORECASE,
)
_LONG_IDENTIFIER = re.compile(r"\b\d{8,}\b")


def contains_prompt_injection(text: str) -> bool:
    """Return whether text resembles an instruction aimed at the generator."""

    return bool(_INSTRUCTION_MARKERS.search(text))


def redact_sensitive_identifiers(text: str) -> str:
    """Redact long numeric identifiers in generated prose.

    Evidence passages themselves are never passed through this function: they
    must remain exact for citation and audit. The structured transaction key
    remains available in ``GroundedExplanation``.
    """

    return _LONG_IDENTIFIER.sub("[REDACTED_IDENTIFIER]", text)


def evidence_has_conflict(passages: Iterable[str]) -> bool:
    """Conservatively flag explicit negation or contradiction language."""

    combined = " ".join(passages)
    return bool(re.search(r"\b(not|unlikely|contradict|inconsistent|instead)\b", combined, re.IGNORECASE))
