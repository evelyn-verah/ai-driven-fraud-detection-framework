"""Input contracts for transaction-time PaySim risk assessment."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


PAYSIM_MODEL_FEATURES = (
    "step",
    "type",
    "amount",
    "oldbalanceOrg",
    "oldbalanceDest",
)
PAYSIM_HISTORY_KEYS = ("nameOrig", "nameDest")
PAYSIM_TARGET = "isFraud"


@dataclass(frozen=True)
class PAYSimTransactionContract:
    """Schema contract for fields available at transaction decision time."""

    model_features: tuple[str, ...] = PAYSIM_MODEL_FEATURES
    history_keys: tuple[str, ...] = PAYSIM_HISTORY_KEYS
    target: str = PAYSIM_TARGET


def validate_transactions(
    frame: pd.DataFrame,
    *,
    require_history_keys: bool = False,
    require_target: bool = False,
) -> None:
    """Validate a PaySim frame without mutating it."""

    contract = PAYSimTransactionContract()
    required = set(contract.model_features)
    if require_history_keys:
        required.update(contract.history_keys)
    if require_target:
        required.add(contract.target)
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise ValueError(f"Missing PaySim transaction columns: {missing}")
    if frame.empty:
        raise ValueError("Transaction frame cannot be empty")
    for column in ("step", "amount", "oldbalanceOrg", "oldbalanceDest"):
        if frame[column].isna().any():
            raise ValueError(f"PaySim column cannot contain nulls: {column}")
    if (frame["amount"] < 0).any():
        raise ValueError("PaySim amount cannot be negative")
    if require_target:
        if frame[contract.target].isna().any() or not frame[contract.target].isin([0, 1]).all():
            raise ValueError("PaySim isFraud must contain only binary non-null values")
