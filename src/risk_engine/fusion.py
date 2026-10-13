"""Configurable, bounded risk-score fusion."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class FusionWeights:
    supervised: float = 1.0
    anomaly_baseline: float = 0.0
    anomaly_behavioral: float = 0.0
    rules: float = 0.0

    def __post_init__(self) -> None:
        values = (self.supervised, self.anomaly_baseline, self.anomaly_behavioral, self.rules)
        if any(value < 0 or not np.isfinite(value) for value in values):
            raise ValueError("Fusion weights must be finite and non-negative")
        if sum(values) <= 0:
            raise ValueError("At least one fusion weight must be positive")


class RiskScoreFusion:
    def __init__(self, weights: FusionWeights) -> None:
        self.weights = weights

    def combine(
        self,
        *,
        supervised: np.ndarray,
        anomaly_baseline: np.ndarray | None = None,
        anomaly_behavioral: np.ndarray | None = None,
        rules: np.ndarray | None = None,
    ) -> np.ndarray:
        components = {
            "supervised": supervised,
            "anomaly_baseline": anomaly_baseline,
            "anomaly_behavioral": anomaly_behavioral,
            "rules": rules,
        }
        weights = self.weights
        weighted: list[np.ndarray] = []
        total = 0.0
        for name, weight in (
            ("supervised", weights.supervised),
            ("anomaly_baseline", weights.anomaly_baseline),
            ("anomaly_behavioral", weights.anomaly_behavioral),
            ("rules", weights.rules),
        ):
            if weight == 0:
                continue
            values = components[name]
            if values is None:
                raise ValueError(f"Missing enabled fusion component: {name}")
            values = np.asarray(values, dtype=float)
            if values.ndim != 1 or not np.isfinite(values).all() or ((values < 0) | (values > 1)).any():
                raise ValueError(f"Fusion component must be finite and bounded: {name}")
            weighted.append(weight * values)
            total += weight
        return np.clip(np.sum(weighted, axis=0) / total, 0.0, 1.0)
