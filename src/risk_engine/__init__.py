"""Module 4: integrated transaction risk assessment components."""

from src.risk_engine.contracts import PAYSimTransactionContract, validate_transactions
from src.risk_engine.fusion import FusionWeights, RiskScoreFusion
from src.risk_engine.normalization import EmpiricalCdfNormalizer
from src.risk_engine.decisions import RiskDecisionPolicy, make_risk_decisions
from src.risk_engine.development_pipeline import (
    DevelopmentSplit,
    apply_calibration,
    calibrate_fusion,
    fit_calibration_normalizers,
    fit_fusion_weights,
    load_score_cache,
    score_development_to_csv,
)
from src.risk_engine.final_architecture import (
    CALIBRATED_RF_ALERT_THRESHOLD,
    CALIBRATED_THRESHOLD_PROVENANCE,
    FINAL_ARCHITECTURE_VERSION,
    FinalRiskAssessment,
    FinalRiskAssessmentConfig,
)
from src.risk_engine.holdout_recovery import (
    calculate_metrics,
    combine_and_validate,
    initialize_recovery,
    resume_suffix,
    verify_frozen_inputs,
    verify_prefix_cache,
    verify_real_model_boundary,
)

__all__ = [
    "EmpiricalCdfNormalizer",
    "FusionWeights",
    "PAYSimTransactionContract",
    "RiskDecisionPolicy",
    "RiskScoreFusion",
    "DevelopmentSplit",
    "apply_calibration",
    "calibrate_fusion",
    "fit_calibration_normalizers",
    "fit_fusion_weights",
    "load_score_cache",
    "make_risk_decisions",
    "score_development_to_csv",
    "validate_transactions",
    "CALIBRATED_RF_ALERT_THRESHOLD",
    "CALIBRATED_THRESHOLD_PROVENANCE",
    "FINAL_ARCHITECTURE_VERSION",
    "FinalRiskAssessment",
    "FinalRiskAssessmentConfig",
    "calculate_metrics",
    "combine_and_validate",
    "initialize_recovery",
    "resume_suffix",
    "verify_frozen_inputs",
    "verify_prefix_cache",
]
