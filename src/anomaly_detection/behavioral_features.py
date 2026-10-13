"""Leakage-safe behavioral features for PaySim transactions.

PaySim's ``step`` is an hourly simulation bucket. Transactions in the same
bucket have no documented ordering, so all rows in a step receive features
from state accumulated through strictly earlier steps only. State is updated
after the complete step has been transformed.
"""

from __future__ import annotations

from collections import deque
from typing import Any

import numpy as np
import pandas as pd


REQUIRED_COLUMNS = {
    "step",
    "type",
    "amount",
    "nameOrig",
    "nameDest",
}

BEHAVIORAL_FEATURES = [
    "sender_txn_count_prior",
    "sender_velocity_3_steps_prior",
    "sender_avg_amount_prior",
    "sender_amount_ratio_to_avg_prior",
    "sender_same_type_count_prior",
    "sender_same_type_share_prior",
    "receiver_txn_count_prior",
    "receiver_avg_amount_prior",
    "receiver_amount_ratio_to_avg_prior",
]


def summarize_activity(
    raw: pd.DataFrame,
    featured: pd.DataFrame,
    train: pd.DataFrame,
    test: pd.DataFrame,
) -> dict[str, object]:
    """Summarize account repetition and historical-feature coverage.

    ``train`` and ``test`` must be chronological partitions of ``raw``. Test
    coverage is deliberately measured against training accounts only, which
    makes the availability claim independent of labels and future rows.
    """

    origin_counts = raw.groupby("nameOrig", observed=True).size()
    destination_counts = raw.groupby("nameDest", observed=True).size()
    train_origins = train["nameOrig"].unique()
    train_destinations = train["nameDest"].unique()
    test_origin_history = test["nameOrig"].isin(train_origins)
    test_destination_history = test["nameDest"].isin(train_destinations)

    feature_rates = {
        feature: {
            "all_rows_nonzero_rate": float(featured[feature].ne(0).mean()),
            "train_rows_nonzero_rate": float(
                featured.loc[train.index, feature].ne(0).mean()
            ),
            "test_rows_nonzero_rate": float(
                featured.loc[test.index, feature].ne(0).mean()
            ),
        }
        for feature in BEHAVIORAL_FEATURES
    }

    return {
        "rows": int(len(raw)),
        "unique_origin_accounts": int(raw["nameOrig"].nunique()),
        "unique_destination_accounts": int(raw["nameDest"].nunique()),
        "origin_accounts_repeated": int((origin_counts > 1).sum()),
        "destination_accounts_repeated": int((destination_counts > 1).sum()),
        "rows_from_repeated_origins_rate": float(
            origin_counts[origin_counts > 1].sum() / len(raw)
        ),
        "rows_to_repeated_destinations_rate": float(
            destination_counts[destination_counts > 1].sum() / len(raw)
        ),
        "train_origin_accounts": int(train["nameOrig"].nunique()),
        "train_destination_accounts": int(train["nameDest"].nunique()),
        "test_rows_with_prior_sender_history": int(test_origin_history.sum()),
        "test_rows_with_prior_sender_history_rate": float(test_origin_history.mean()),
        "test_rows_with_prior_receiver_history": int(test_destination_history.sum()),
        "test_rows_with_prior_receiver_history_rate": float(
            test_destination_history.mean()
        ),
        "test_senders_seen_in_training": int(
            test.loc[test_origin_history, "nameOrig"].nunique()
        ),
        "test_receivers_seen_in_training": int(
            test.loc[test_destination_history, "nameDest"].nunique()
        ),
        "behavioral_feature_nonzero_rates": feature_rates,
        "history_definition": (
            "Training-account membership is measured using rows from earlier steps only; "
            "same-step rows are not used as history."
        ),
    }


def _safe_ratio(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    """Return a finite ratio, using zero when no historical denominator exists."""

    return (numerator / denominator.replace(0, np.nan)).replace(
        [np.inf, -np.inf], np.nan
    ).fillna(0.0)


def add_behavioral_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add transaction-time behavioral features to a PaySim frame.

    The returned frame preserves the input row order and index. For each
    simulation step, feature values are calculated before any transaction in
    that step updates the history. This makes the result independent of the
    row ordering within an hour and prevents same-step future information from
    leaking into another transaction's features.

    Parameters
    ----------
    df:
        PaySim rows containing at least the columns in ``REQUIRED_COLUMNS``.

    Returns
    -------
    pandas.DataFrame
        A copy of ``df`` with the numeric columns in ``BEHAVIORAL_FEATURES``.
    """

    missing = REQUIRED_COLUMNS.difference(df.columns)
    if missing:
        raise ValueError(f"Missing PaySim behavioral columns: {sorted(missing)}")
    if df.empty:
        return df.copy().assign(
            **{feature: pd.Series(dtype="float64") for feature in BEHAVIORAL_FEATURES}
        )

    work = df.copy()
    for column in ("step", "amount"):
        if work[column].isna().any():
            raise ValueError(f"{column} cannot contain nulls")
    feature_values: dict[str, pd.Series] = {
        feature: pd.Series(0.0, index=work.index) for feature in BEHAVIORAL_FEATURES
    }

    sender_count: dict[Any, int] = {}
    sender_amount_sum: dict[Any, float] = {}
    sender_type_count: dict[tuple[Any, Any], int] = {}
    receiver_count: dict[Any, int] = {}
    receiver_amount_sum: dict[Any, float] = {}
    sender_velocity: dict[Any, int] = {}
    velocity_history: deque[dict[Any, int]] = deque()

    for _, current in work.groupby("step", sort=True, observed=True):
        current_senders = current["nameOrig"]
        current_receivers = current["nameDest"]

        prior_sender_count = current_senders.map(sender_count).fillna(0).astype(float)
        prior_sender_sum = current_senders.map(sender_amount_sum).fillna(0.0)
        prior_sender_avg = _safe_ratio(prior_sender_sum, prior_sender_count)
        prior_sender_velocity = current_senders.map(sender_velocity).fillna(0).astype(float)

        prior_same_type = pd.Series(
            [
                sender_type_count.get((sender, transaction_type), 0)
                for sender, transaction_type in zip(
                    current["nameOrig"], current["type"], strict=True
                )
            ],
            index=current.index,
            dtype="float64",
        )

        prior_receiver_count = current_receivers.map(receiver_count).fillna(0).astype(float)
        prior_receiver_sum = current_receivers.map(receiver_amount_sum).fillna(0.0)
        prior_receiver_avg = _safe_ratio(prior_receiver_sum, prior_receiver_count)

        feature_values["sender_txn_count_prior"].loc[current.index] = prior_sender_count
        feature_values["sender_velocity_3_steps_prior"].loc[current.index] = prior_sender_velocity
        feature_values["sender_avg_amount_prior"].loc[current.index] = prior_sender_avg
        feature_values["sender_amount_ratio_to_avg_prior"].loc[current.index] = _safe_ratio(
            current["amount"].astype(float), prior_sender_avg
        )
        feature_values["sender_same_type_count_prior"].loc[current.index] = prior_same_type
        feature_values["sender_same_type_share_prior"].loc[current.index] = _safe_ratio(
            prior_same_type, prior_sender_count
        )
        feature_values["receiver_txn_count_prior"].loc[current.index] = prior_receiver_count
        feature_values["receiver_avg_amount_prior"].loc[current.index] = prior_receiver_avg
        feature_values["receiver_amount_ratio_to_avg_prior"].loc[current.index] = _safe_ratio(
            current["amount"].astype(float), prior_receiver_avg
        )

        current_sender_counts = current.groupby(
            "nameOrig", sort=False, observed=True
        ).size().to_dict()
        current_sender_sums = current.groupby(
            "nameOrig", sort=False, observed=True
        )["amount"].sum().to_dict()
        current_receiver_counts = current.groupby(
            "nameDest", sort=False, observed=True
        ).size().to_dict()
        current_receiver_sums = current.groupby(
            "nameDest", sort=False, observed=True
        )["amount"].sum().to_dict()
        current_type_counts = (
            current.groupby(
                ["nameOrig", "type"], sort=False, observed=True
            ).size().to_dict()
        )

        for sender, count in current_sender_counts.items():
            sender_count[sender] = sender_count.get(sender, 0) + int(count)
        for sender, amount_sum in current_sender_sums.items():
            sender_amount_sum[sender] = sender_amount_sum.get(sender, 0.0) + float(amount_sum)
        for key, count in current_type_counts.items():
            sender_type_count[key] = sender_type_count.get(key, 0) + int(count)
        for receiver, count in current_receiver_counts.items():
            receiver_count[receiver] = receiver_count.get(receiver, 0) + int(count)
        for receiver, amount_sum in current_receiver_sums.items():
            receiver_amount_sum[receiver] = receiver_amount_sum.get(receiver, 0.0) + float(amount_sum)

        for sender, count in current_sender_counts.items():
            sender_velocity[sender] = sender_velocity.get(sender, 0) + int(count)
        velocity_history.append({sender: int(count) for sender, count in current_sender_counts.items()})
        if len(velocity_history) > 3:
            expired = velocity_history.popleft()
            for sender, count in expired.items():
                remaining = sender_velocity[sender] - count
                if remaining:
                    sender_velocity[sender] = remaining
                else:
                    sender_velocity.pop(sender, None)

    for feature, values in feature_values.items():
        work[feature] = values.astype("float32")
    return work
