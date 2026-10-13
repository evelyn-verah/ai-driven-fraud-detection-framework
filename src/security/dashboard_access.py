"""Deny-by-default access and analyst-safe projections for the local dashboard.

This is a local research-prototype facade. It does not authenticate a person;
the caller must provide an out-of-band trusted local identity marker before a
session can be issued. Frozen dashboard and monitoring modules remain intact.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from .storage_security import secure_read_sqlite, secure_save_review


class AuthorizationError(PermissionError):
    """Raised when no trusted context or permission is available."""


_ISSUANCE_MARKER = object()
_ROLES = frozenset({"Viewer", "Analyst", "Administrator"})
_PERMISSIONS = {
    "Viewer": frozenset({"dashboard.read", "transaction.detail"}),
    "Analyst": frozenset({"dashboard.read", "transaction.detail", "review.submit", "feedback.read"}),
    "Administrator": frozenset({"dashboard.read", "transaction.detail", "feedback.read", "diagnostics.read"}),
}
_SENSITIVE_KEYS = frozenset({
    "isfraud", "isflaggedfraud", "nameorig", "namedest", "reviewer",
    "reviewer_label", "notes", "review_notes", "label", "labels",
    "ground_truth", "fraud_label", "verified_fraud",
})
_SAFE_SCORE_FIELDS = (
    "row_id", "step", "fraud_probability", "baseline_anomaly_intensity",
    "behavioral_anomaly_intensity", "rule_score_context", "alert",
)
_SAFE_METADATA_FIELDS = (
    "row_id", "step", "type", "amount", "oldbalanceOrg", "newbalanceOrig",
    "oldbalanceDest", "newbalanceDest",
)


@dataclass(frozen=True)
class DashboardContext:
    role: str
    authenticated: bool = False
    _marker: object | None = None


def issue_local_context(role: str, *, trusted_local_identity: bool = False) -> DashboardContext:
    """Issue a simulated local context only after an out-of-band trust check."""
    if not trusted_local_identity or not isinstance(role, str) or role not in _ROLES:
        raise AuthorizationError("trusted local identity is required")
    return DashboardContext(role=role, authenticated=True, _marker=_ISSUANCE_MARKER)


def require_permission(context: DashboardContext | None, permission: str) -> None:
    if not isinstance(context, DashboardContext) or context._marker is not _ISSUANCE_MARKER:
        raise AuthorizationError("authorization context is missing or untrusted")
    if not context.authenticated or context.role not in _ROLES:
        raise AuthorizationError("authorization context is invalid")
    if permission not in _PERMISSIONS[context.role]:
        raise AuthorizationError("permission denied")


def analyst_safe_scores(rows: Any) -> Any:
    """Project a DataFrame-like score table to the explicit safe allowlist."""
    columns = getattr(rows, "columns", None)
    if columns is None or not set(_SAFE_SCORE_FIELDS).issubset(columns):
        raise AuthorizationError("score projection is unavailable")
    return rows.loc[:, list(_SAFE_SCORE_FIELDS)].copy()


def authorized_scores(context: DashboardContext | None, rows: Any) -> Any:
    require_permission(context, "dashboard.read")
    return analyst_safe_scores(rows)


def analyst_safe_detail(detail: Mapping[str, Any]) -> dict[str, Any]:
    """Project transaction detail data without labels, identities, or notes."""
    if not isinstance(detail, Mapping):
        raise AuthorizationError("transaction detail is unavailable")
    metadata = detail.get("metadata")
    if not isinstance(metadata, Mapping):
        raise AuthorizationError("transaction detail is unavailable")
    safe: dict[str, Any] = {
        "metadata": {key: metadata[key] for key in _SAFE_METADATA_FIELDS if key in metadata},
    }
    intelligence = detail.get("intelligence")
    if isinstance(intelligence, Mapping):
        allowed_intelligence = ("context", "explanation", "limitation")
        safe_intelligence: dict[str, Any] = {}
        for key in allowed_intelligence:
            value = intelligence.get(key)
            if key == "context" and isinstance(value, Mapping):
                safe_intelligence[key] = {
                    field: value[field] for field in (
                        "fraud_probability", "alert", "threshold",
                        "baseline_anomaly_intensity", "behavioral_anomaly_intensity",
                        "rule_score_context", "threshold_provenance",
                        "module4_architecture_version", "model_versions",
                    ) if field in value
                }
            elif key == "explanation" and isinstance(value, Mapping):
                safe_intelligence[key] = {
                    field: value[field] for field in (
                        "observed_facts", "model_indicators", "possible_interpretations",
                        "uncertainty_and_limitations", "suggested_review_steps",
                        "retrieved_evidence",
                    ) if field in value
                }
            elif key == "limitation" and isinstance(value, str):
                safe_intelligence[key] = value
        safe["intelligence"] = safe_intelligence
    return safe


def authorized_detail(context: DashboardContext | None, detail: Mapping[str, Any]) -> dict[str, Any]:
    require_permission(context, "transaction.detail")
    return analyst_safe_detail(detail)


def safe_feedback_summary(context: DashboardContext | None, database: str, *, trusted_root: str,
                          production_only: bool = True, demonstration_path: str | None = None) -> dict[str, Any]:
    require_permission(context, "feedback.read")
    events = secure_read_sqlite(database, trusted_root=trusted_root,
                                production_only=production_only,
                                demonstration_path=demonstration_path)
    return {"event_count": len(events), "status_counts": dict(Counter(event["status"] for event in events))}


def submit_review(context: DashboardContext | None, database: str, row_id: int, status: str,
                  reviewer_label: str, notes: str | None, *, trusted_root: str,
                  demonstration_path: str | None = None):
    require_permission(context, "review.submit")
    return secure_save_review(database, row_id, status, reviewer_label, notes,
                              trusted_root=trusted_root, production_only=True,
                              demonstration_path=demonstration_path)


def denied_sensitive_keys(mapping: Mapping[str, Any]) -> set[str]:
    """Return sensitive keys present in a mapping, for regression assertions."""
    if not isinstance(mapping, Mapping):
        return set()
    return {str(key) for key in mapping if str(key).casefold() in _SENSITIVE_KEYS}


__all__ = [
    "AuthorizationError", "DashboardContext", "analyst_safe_detail",
    "analyst_safe_scores", "authorized_detail", "authorized_scores",
    "denied_sensitive_keys", "issue_local_context",
    "require_permission", "safe_feedback_summary", "submit_review",
]
