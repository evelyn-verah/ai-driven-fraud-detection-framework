"""Development-fitted normalization for heterogeneous model scores."""

from __future__ import annotations

import numpy as np


class EmpiricalCdfNormalizer:
    """Map anomaly scores to [0, 1] using a frozen development distribution."""

    def __init__(self) -> None:
        self._sorted_scores: np.ndarray | None = None

    def fit(self, scores: np.ndarray) -> "EmpiricalCdfNormalizer":
        values = np.asarray(scores, dtype=float)
        if values.ndim != 1 or len(values) == 0 or not np.isfinite(values).all():
            raise ValueError("Normalization scores must be finite and non-empty")
        self._sorted_scores = np.sort(values)
        return self

    def transform(self, scores: np.ndarray) -> np.ndarray:
        if self._sorted_scores is None:
            raise RuntimeError("Normalizer must be fitted on development scores first")
        values = np.asarray(scores, dtype=float)
        if values.ndim != 1 or not np.isfinite(values).all():
            raise ValueError("Scores must be finite and one-dimensional")
        ranks = np.searchsorted(self._sorted_scores, values, side="right")
        return np.clip(ranks / len(self._sorted_scores), 0.0, 1.0)
