"""Risk tiers, alert decisions, and explanation provenance."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class RiskDecisionPolicy:
    alert_threshold: float = 0.8
    high_threshold: float = 0.8
    medium_threshold: float = 0.5

    def __post_init__(self) -> None:
        values = (self.alert_threshold, self.high_threshold, self.medium_threshold)
        if any(value < 0 or value > 1 or not np.isfinite(value) for value in values):
            raise ValueError("Risk thresholds must be in [0, 1]")
        if not self.high_threshold >= self.medium_threshold:
            raise ValueError("high_threshold must be >= medium_threshold")


def make_risk_decisions(
    risk_score: np.ndarray,
    *,
    policy: RiskDecisionPolicy,
    component_scores: dict[str, np.ndarray] | None = None,
    rule_reasons: list[list[str]] | None = None,
) -> pd.DataFrame:
    scores = np.asarray(risk_score, dtype=float)
    if scores.ndim != 1 or not np.isfinite(scores).all() or ((scores < 0) | (scores > 1)).any():
        raise ValueError("risk_score must be finite and bounded in [0, 1]")
    if rule_reasons is not None and len(rule_reasons) != len(scores):
        raise ValueError("rule_reasons must align with risk_score")
    component_scores = component_scores or {}
    for name, values in component_scores.items():
        values = np.asarray(values, dtype=float)
        if len(values) != len(scores) or not np.isfinite(values).all():
            raise ValueError(f"Component score does not align: {name}")

    explanations: list[list[str]] = []
    for position in range(len(scores)):
        reasons = [] if rule_reasons is None else list(rule_reasons[position])
        for name, values in component_scores.items():
            if values[position] >= 0.5:
                reasons.append(f"signal:{name}")
        explanations.append(sorted(set(reasons)))

    tiers = np.where(
        scores >= policy.high_threshold,
        "high",
        np.where(scores >= policy.medium_threshold, "medium", "low"),
    )
    return pd.DataFrame(
        {
            "risk_score": scores,
            "risk_tier": tiers,
            "alert": scores >= policy.alert_threshold,
            "explanations": explanations,
        }
    )
