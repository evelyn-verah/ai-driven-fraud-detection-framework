"""Validated read-only bridge from frozen scores to Module 5 intelligence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from src.fraud_intelligence.integration import IntegratedRiskIntelligence, explain_module4_record
from src.fraud_intelligence.retrieval import RetrievalIndex
from src.risk_engine.final_architecture import FinalRiskAssessmentConfig

from .data_access import DataValidationError, ScoreCache, lookup_metadata


@dataclass(frozen=True)
class TransactionDetails:
    row_id: int
    metadata: dict[str, Any]
    intelligence: IntegratedRiskIntelligence
    limitation: str


def build_transaction_details(
    row_id: int,
    score_cache: ScoreCache,
    retrieval_index: RetrievalIndex,
    *,
    raw_path: str | None = None,
    metadata_index=None,
) -> TransactionDetails:
    """Load one aligned transaction and generate grounded intelligence.

    The persisted holdout cache does not contain per-transaction rule IDs or
    behavioral feature columns.  The adapter therefore receives an explicit
    empty rule sequence and no behavioral features; this records unavailable
    context as unavailable rather than inventing it.  The rule score itself,
    model provenance, threshold, and all stored scores remain exact.
    """
    if isinstance(row_id, bool) or not isinstance(row_id, int):
        raise ValueError("row_id must be an integer")
    if row_id < 0 or row_id >= len(score_cache.frame):
        raise ValueError("row_id is outside the frozen holdout cache")
    lookup_kwargs = {"raw_path": raw_path} if raw_path is not None else {}
    if metadata_index is not None:
        lookup_kwargs["metadata_index"] = metadata_index
    metadata_frame = lookup_metadata([row_id], score_cache, **lookup_kwargs)
    if len(metadata_frame) != 1 or int(metadata_frame.iloc[0]["row_id"]) != row_id:
        raise DataValidationError("selected metadata row does not match the requested row_id")
    metadata_row = metadata_frame.iloc[0]
    score_row = score_cache.frame.loc[score_cache.frame["row_id"] == row_id].iloc[0]
    if int(metadata_row["step"]) != int(score_row["step"]) or int(metadata_row["isFraud"]) != int(score_row["isFraud"]):
        raise DataValidationError("selected metadata and score record are misaligned")
    config = FinalRiskAssessmentConfig()
    record = {
        "row_id": row_id,
        "step": int(score_row["step"]),
        "amount": float(metadata_row["amount"]),
        "transaction_type": str(metadata_row["type"]),
        "fraud_probability": float(score_row["fraud_probability"]),
        "baseline_anomaly_intensity": float(score_row["baseline_anomaly_intensity"]),
        "behavioral_anomaly_intensity": float(score_row["behavioral_anomaly_intensity"]),
        "rule_score_context": float(score_row["rule_score_context"]),
        "alert": bool(score_row["alert"]),
        "threshold": config.fraud_alert_threshold,
        "threshold_provenance": config.threshold_provenance,
        "module4_architecture_version": config.architecture_version,
        "model_versions": {
            "supervised": config.supervised_model_version,
            "baseline_anomaly": config.baseline_anomaly_model_version,
            "behavioral_anomaly": config.behavioral_anomaly_model_version,
        },
        # The score cache contains no rule IDs; this is an explicit absence,
        # and the explanation labels them "none supplied".
        "triggered_rules": (),
        "behavioral_features": None,
    }
    intelligence = explain_module4_record(record, retrieval_index, top_k=5)
    display_metadata = {
        "row_id": row_id,
        "step": int(metadata_row["step"]),
        "type": str(metadata_row["type"]),
        "amount": float(metadata_row["amount"]),
        "oldbalanceOrg": float(metadata_row["oldbalanceOrg"]),
        "newbalanceOrig": float(metadata_row["newbalanceOrig"]),
        "oldbalanceDest": float(metadata_row["oldbalanceDest"]),
        "newbalanceDest": float(metadata_row["newbalanceDest"]),
    }
    return TransactionDetails(
        row_id=row_id,
        metadata=display_metadata,
        intelligence=intelligence,
        limitation="Persisted holdout scores contain rule score context but no per-transaction rule IDs or behavioral feature columns; those fields were not inferred.",
    )
