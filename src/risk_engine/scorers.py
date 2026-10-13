"""Adapters around the frozen supervised and anomaly model artifacts."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from src.anomaly_detection.behavioral_features import BEHAVIORAL_FEATURES
from src.risk_engine.contracts import PAYSIM_MODEL_FEATURES, validate_transactions


ANOMALY_BASE_FEATURES = ("amount", "oldbalanceOrg", "oldbalanceDest", "step")
ANOMALY_BEHAVIORAL_FEATURES = ANOMALY_BASE_FEATURES + tuple(BEHAVIORAL_FEATURES)


def _check_scores(scores: np.ndarray, *, bounded: bool) -> np.ndarray:
    values = np.asarray(scores, dtype=float)
    if values.ndim != 1 or not np.isfinite(values).all():
        raise ValueError("Model scores must be a finite one-dimensional array")
    if bounded and ((values < 0).any() or (values > 1).any()):
        raise ValueError("Fraud probabilities must be in [0, 1]")
    return values


@dataclass
class SupervisedFraudScorer:
    model: object

    def score(self, frame: pd.DataFrame) -> np.ndarray:
        validate_transactions(frame)
        probabilities = self.model.predict_proba(frame[list(PAYSIM_MODEL_FEATURES)])[:, 1]
        return _check_scores(probabilities, bounded=True)


@dataclass
class IsolationForestScorer:
    model: object
    feature_columns: tuple[str, ...]

    def score(self, frame: pd.DataFrame) -> np.ndarray:
        missing = sorted(set(self.feature_columns).difference(frame.columns))
        if missing:
            raise ValueError(f"Missing anomaly feature columns: {missing}")
        if hasattr(self.model, "named_steps") and "model" in self.model.named_steps:
            transformed = self.model[:-1].transform(frame[list(self.feature_columns)])
            raw_scores = -self.model.named_steps["model"].score_samples(transformed)
        elif isinstance(self.model, dict) and {"preprocessor", "model"}.issubset(self.model):
            transformed = self.model["preprocessor"].transform(frame[list(self.feature_columns)])
            raw_scores = -self.model["model"].score_samples(transformed)
        else:
            raise TypeError("Unsupported Isolation Forest artifact structure")
        return _check_scores(raw_scores, bounded=False)
