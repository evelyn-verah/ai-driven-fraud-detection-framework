"""Versioned Module 4 Stage 4 transaction risk-assessment interface.

Random Forest probability is the sole alert-driving score. Isolation Forest
outputs are independent anomaly intensities (higher means more anomalous), not
fraud probabilities, and rules are contextual evidence only.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from src.risk_engine.behavioral_state import ChronologicalBehavioralProcessor
from src.risk_engine.contracts import validate_transactions
from src.risk_engine.rules import PaySimRuleConfig, evaluate_paysim_rules
from src.risk_engine.scorers import IsolationForestScorer, SupervisedFraudScorer
from src.risk_engine.trusted_artifacts import load_trusted_model


FINAL_ARCHITECTURE_VERSION = "module4_stage4_rf_primary_v1"
CALIBRATED_RF_ALERT_THRESHOLD = 0.3494391872980995
CALIBRATED_THRESHOLD_PROVENANCE = "Module 4 development calibration, steps 46-200; maximum calibration F1; frozen before steps 201-377 evaluation"


@dataclass(frozen=True)
class FinalRiskAssessmentConfig:
    """Immutable model and threshold provenance for the final architecture."""

    architecture_version: str = FINAL_ARCHITECTURE_VERSION
    fraud_alert_threshold: float = CALIBRATED_RF_ALERT_THRESHOLD
    threshold_provenance: str = CALIBRATED_THRESHOLD_PROVENANCE
    supervised_model_version: str = "paysim_v2_random_forest_frozen"
    baseline_anomaly_model_version: str = "anomaly_detection_behavioral_1m_baseline_frozen"
    behavioral_anomaly_model_version: str = "anomaly_detection_behavioral_1m_behavioral_frozen"

    def __post_init__(self) -> None:
        if not np.isfinite(self.fraud_alert_threshold) or not 0 <= self.fraud_alert_threshold <= 1:
            raise ValueError("fraud_alert_threshold must be in [0, 1]")
        if not self.threshold_provenance.strip():
            raise ValueError("threshold_provenance is required")


@dataclass
class FinalRiskAssessment:
    """Score complete chronological steps with RF-primary alert semantics."""

    supervised_model: object
    baseline_anomaly_model: object
    behavioral_anomaly_model: object
    config: FinalRiskAssessmentConfig = FinalRiskAssessmentConfig()
    rule_config: PaySimRuleConfig = PaySimRuleConfig()

    def __post_init__(self) -> None:
        self._behavioral_state = ChronologicalBehavioralProcessor()
        self._supervised = SupervisedFraudScorer(self.supervised_model)
        self._baseline = IsolationForestScorer(
            self.baseline_anomaly_model,
            ("amount", "oldbalanceOrg", "oldbalanceDest", "step"),
        )
        self._behavioral = IsolationForestScorer(
            self.behavioral_anomaly_model,
            (
                "amount", "oldbalanceOrg", "oldbalanceDest", "step",
                "sender_txn_count_prior", "sender_velocity_3_steps_prior",
                "sender_avg_amount_prior", "sender_amount_ratio_to_avg_prior",
                "sender_same_type_count_prior", "sender_same_type_share_prior",
                "receiver_txn_count_prior", "receiver_avg_amount_prior",
                "receiver_amount_ratio_to_avg_prior",
            ),
        )

    @classmethod
    def from_joblib_paths(
        cls,
        supervised_path: str | Path,
        baseline_anomaly_path: str | Path,
        behavioral_anomaly_path: str | Path,
        *,
        config: FinalRiskAssessmentConfig = FinalRiskAssessmentConfig(),
    ) -> "FinalRiskAssessment":
        """Load frozen artifacts without fitting or modifying them."""

        return cls(
            supervised_model=load_trusted_model(supervised_path, model_role="supervised"),
            baseline_anomaly_model=load_trusted_model(baseline_anomaly_path, model_role="baseline_anomaly"),
            behavioral_anomaly_model=load_trusted_model(behavioral_anomaly_path, model_role="behavioral_anomaly"),
            config=config,
        )

    def assess_step(self, transactions: pd.DataFrame) -> pd.DataFrame:
        """Assess one complete step, preserving input row order and index.

        ``isFraud`` is accepted for offline validation but is never read by any
        scorer or decision. The behavioral processor commits state only after
        transforming the complete step, preventing same-step leakage.
        """

        featured = self.process_history_step(transactions)
        probability = self._supervised.score(featured)
        baseline_intensity = self._baseline.score(featured)
        behavioral_intensity = self._behavioral.score(featured)
        rule_score, rule_reasons = evaluate_paysim_rules(
            transactions, behavioral=featured, config=self.rule_config
        )
        alert = probability >= self.config.fraud_alert_threshold
        explanations = [
            self._explanation(
                probability=float(probability[pos]),
                alert=bool(alert[pos]),
                baseline=float(baseline_intensity[pos]),
                behavioral=float(behavioral_intensity[pos]),
                rules=rule_reasons[pos],
            )
            for pos in range(len(transactions))
        ]
        result = pd.DataFrame(
            {
                "fraud_probability": probability,
                "baseline_anomaly_intensity": baseline_intensity,
                "behavioral_anomaly_intensity": behavioral_intensity,
                "triggered_rules": rule_reasons,
                "rule_score_context": rule_score,
                "alert": alert,
                "explanation": explanations,
            },
            index=transactions.index,
        )
        return result

    def process_history_step(self, transactions: pd.DataFrame) -> pd.DataFrame:
        """Validate and transform a complete step without model scoring.

        Recovery workflows use this method to rebuild behavioral state for
        already-scored prefix rows without rescoring those rows.
        """

        validate_transactions(transactions, require_history_keys=True)
        return self._behavioral_state.process_step(transactions)

    def process_history_state_only(self, transactions: pd.DataFrame) -> None:
        """Rebuild behavioral state without materializing historical features."""

        validate_transactions(transactions, require_history_keys=True)
        self._behavioral_state.process_state_only(transactions)

    def _explanation(
        self, *, probability: float, alert: bool, baseline: float,
        behavioral: float, rules: list[str],
    ) -> str:
        decision = "alert" if alert else "no alert"
        evidence = [
            f"fraud probability {probability:.6f} ({decision}; threshold {self.config.fraud_alert_threshold:.15f})",
            f"baseline anomaly intensity {baseline:.6f} (higher means more anomalous; not a probability)",
            f"behavioral anomaly intensity {behavioral:.6f} (higher means more anomalous; not a probability)",
        ]
        evidence.append("rules triggered: " + (", ".join(rules) if rules else "none"))
        return "; ".join(evidence) + "."


__all__ = [
    "CALIBRATED_RF_ALERT_THRESHOLD",
    "CALIBRATED_THRESHOLD_PROVENANCE",
    "FINAL_ARCHITECTURE_VERSION",
    "FinalRiskAssessment",
    "FinalRiskAssessmentConfig",
]
