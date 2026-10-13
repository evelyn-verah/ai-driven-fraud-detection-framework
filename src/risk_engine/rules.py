"""Transparent PaySim-supported transaction-time risk rules."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from src.risk_engine.contracts import validate_transactions


@dataclass(frozen=True)
class PaySimRuleConfig:
    receiver_ratio_threshold: float = 3.0


def evaluate_paysim_rules(
    frame: pd.DataFrame,
    *,
    behavioral: pd.DataFrame | None = None,
    config: PaySimRuleConfig = PaySimRuleConfig(),
) -> tuple[np.ndarray, list[list[str]]]:
    """Return bounded rule scores and auditable rule identifiers."""

    validate_transactions(frame)
    if config.receiver_ratio_threshold <= 0:
        raise ValueError("receiver_ratio_threshold must be positive")
    score = np.zeros(len(frame), dtype=float)
    reasons: list[list[str]] = [[] for _ in range(len(frame))]

    amount_exceeds_origin = frame["amount"].to_numpy() > frame["oldbalanceOrg"].to_numpy()
    for position in np.flatnonzero(amount_exceeds_origin):
        score[position] += 0.5
        reasons[position].append("amount_exceeds_oldbalanceOrg")

    if behavioral is not None:
        if len(behavioral) != len(frame):
            raise ValueError("Behavioral and transaction frames must have equal length")
        required = {
            "receiver_txn_count_prior",
            "receiver_amount_ratio_to_avg_prior",
        }
        missing = sorted(required.difference(behavioral.columns))
        if missing:
            raise ValueError(f"Missing behavioral rule columns: {missing}")
        unusual_receiver = (
            behavioral["receiver_txn_count_prior"].to_numpy() > 0
        ) & (
            behavioral["receiver_amount_ratio_to_avg_prior"].to_numpy()
            >= config.receiver_ratio_threshold
        )
        for position in np.flatnonzero(unusual_receiver):
            score[position] += 0.5
            reasons[position].append("amount_high_vs_prior_receiver_average")

    return np.clip(score, 0.0, 1.0), reasons
