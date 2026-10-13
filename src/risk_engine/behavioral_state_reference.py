"""Stateful, step-batched PaySim behavioral feature generation."""

from __future__ import annotations

from collections import deque
from typing import Any

import numpy as np
import pandas as pd

from src.anomaly_detection.behavioral_features import BEHAVIORAL_FEATURES
from src.risk_engine.contracts import validate_transactions


def iter_complete_steps(
    path: str,
    *,
    chunksize: int = 100_000,
    include_target: bool = False,
) -> Any:
    """Yield complete PaySim steps while retaining at most one boundary step.

    The final chunk is yielded normally. A caller can feed each yielded frame
    directly to ``ChronologicalBehavioralProcessor.process_step``. The input
    CSV must be ordered by ``step`` as the PaySim source file is.
    """

    if chunksize < 1:
        raise ValueError("chunksize must be positive")
    pending: list[pd.DataFrame] = []
    pending_step: Any | None = None
    usecols = [
        "step",
        "type",
        "amount",
        "oldbalanceOrg",
        "oldbalanceDest",
        "nameOrig",
        "nameDest",
    ]
    if include_target:
        usecols.append("isFraud")
    dtypes = {
        "step": "int16",
        "type": "category",
        "amount": "float32",
        "oldbalanceOrg": "float32",
        "oldbalanceDest": "float32",
        "nameOrig": "string",
        "nameDest": "string",
    }
    if include_target:
        dtypes["isFraud"] = "int8"
    for chunk in pd.read_csv(path, usecols=usecols, dtype=dtypes, chunksize=chunksize):
        for step, step_frame in chunk.groupby("step", sort=True, observed=True):
            if pending_step is None:
                pending_step = step
            if step != pending_step:
                yield pd.concat(pending, copy=False)
                pending = []
                pending_step = step
            pending.append(step_frame)
    if pending:
        yield pd.concat(pending, copy=False)


class ReferenceChronologicalBehavioralProcessor:
    """Generate the existing behavioral features one complete step at a time.

    Callers must provide a complete simulation step to ``process_step``. The
    state update happens after all rows in that step are transformed, so row
    ordering and same-step visibility cannot introduce leakage.
    """

    def __init__(self) -> None:
        self._sender_count: dict[Any, int] = {}
        self._sender_amount_sum: dict[Any, float] = {}
        self._sender_type_count: dict[tuple[Any, Any], int] = {}
        self._receiver_count: dict[Any, int] = {}
        self._receiver_amount_sum: dict[Any, float] = {}
        self._sender_velocity: dict[Any, int] = {}
        self._velocity_history: deque[dict[Any, int]] = deque()
        self._last_step: Any | None = None

    @staticmethod
    def _safe_ratio(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
        return (numerator / denominator.replace(0, np.nan)).replace(
            [np.inf, -np.inf], np.nan
        ).fillna(0.0)

    def process_step(self, step_frame: pd.DataFrame) -> pd.DataFrame:
        """Transform one complete step and then commit its state."""

        validate_transactions(step_frame, require_history_keys=True)
        if step_frame["step"].nunique() != 1:
            raise ValueError("process_step requires exactly one simulation step")
        step = step_frame["step"].iloc[0]
        if self._last_step is not None and step <= self._last_step:
            raise ValueError("Simulation steps must be strictly increasing")

        work = step_frame.copy()
        current_senders = work["nameOrig"]
        current_receivers = work["nameDest"]
        prior_sender_count = current_senders.map(self._sender_count).fillna(0).astype(float)
        prior_sender_sum = current_senders.map(self._sender_amount_sum).fillna(0.0)
        prior_sender_avg = self._safe_ratio(prior_sender_sum, prior_sender_count)
        prior_sender_velocity = current_senders.map(self._sender_velocity).fillna(0).astype(float)
        prior_same_type = pd.Series(
            [
                self._sender_type_count.get((sender, transaction_type), 0)
                for sender, transaction_type in zip(
                    work["nameOrig"], work["type"], strict=True
                )
            ],
            index=work.index,
            dtype="float64",
        )
        prior_receiver_count = current_receivers.map(self._receiver_count).fillna(0).astype(float)
        prior_receiver_sum = current_receivers.map(self._receiver_amount_sum).fillna(0.0)
        prior_receiver_avg = self._safe_ratio(prior_receiver_sum, prior_receiver_count)

        work["sender_txn_count_prior"] = prior_sender_count.astype("float32")
        work["sender_velocity_3_steps_prior"] = prior_sender_velocity.astype("float32")
        work["sender_avg_amount_prior"] = prior_sender_avg.astype("float32")
        work["sender_amount_ratio_to_avg_prior"] = self._safe_ratio(
            work["amount"].astype(float), prior_sender_avg
        ).astype("float32")
        work["sender_same_type_count_prior"] = prior_same_type.astype("float32")
        work["sender_same_type_share_prior"] = self._safe_ratio(
            prior_same_type, prior_sender_count
        ).astype("float32")
        work["receiver_txn_count_prior"] = prior_receiver_count.astype("float32")
        work["receiver_avg_amount_prior"] = prior_receiver_avg.astype("float32")
        work["receiver_amount_ratio_to_avg_prior"] = self._safe_ratio(
            work["amount"].astype(float), prior_receiver_avg
        ).astype("float32")

        sender_counts = work.groupby("nameOrig", sort=False, observed=True).size().to_dict()
        sender_sums = work.groupby("nameOrig", sort=False, observed=True)["amount"].sum().to_dict()
        receiver_counts = work.groupby("nameDest", sort=False, observed=True).size().to_dict()
        receiver_sums = work.groupby("nameDest", sort=False, observed=True)["amount"].sum().to_dict()
        type_counts = work.groupby(
            ["nameOrig", "type"], sort=False, observed=True
        ).size().to_dict()
        for sender, count in sender_counts.items():
            self._sender_count[sender] = self._sender_count.get(sender, 0) + int(count)
        for sender, amount_sum in sender_sums.items():
            self._sender_amount_sum[sender] = self._sender_amount_sum.get(sender, 0.0) + float(amount_sum)
        for key, count in type_counts.items():
            self._sender_type_count[key] = self._sender_type_count.get(key, 0) + int(count)
        for receiver, count in receiver_counts.items():
            self._receiver_count[receiver] = self._receiver_count.get(receiver, 0) + int(count)
        for receiver, amount_sum in receiver_sums.items():
            self._receiver_amount_sum[receiver] = self._receiver_amount_sum.get(receiver, 0.0) + float(amount_sum)
        for sender, count in sender_counts.items():
            self._sender_velocity[sender] = self._sender_velocity.get(sender, 0) + int(count)
        self._velocity_history.append({sender: int(count) for sender, count in sender_counts.items()})
        if len(self._velocity_history) > 3:
            expired = self._velocity_history.popleft()
            for sender, count in expired.items():
                remaining = self._sender_velocity[sender] - count
                if remaining:
                    self._sender_velocity[sender] = remaining
                else:
                    self._sender_velocity.pop(sender, None)
        self._last_step = step
        return work

    def transform_ordered(self, frame: pd.DataFrame) -> pd.DataFrame:
        """Transform an in-memory ordered frame for tests and small samples."""

        validate_transactions(frame, require_history_keys=True)
        outputs = [
            self.process_step(step_frame)
            for _, step_frame in frame.groupby("step", sort=True, observed=True)
        ]
        return pd.concat(outputs).loc[frame.index]


__all__ = ["BEHAVIORAL_FEATURES", "ReferenceChronologicalBehavioralProcessor", "iter_complete_steps"]
