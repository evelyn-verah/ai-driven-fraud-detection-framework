"""Configuration for the Module 6 dashboard prototype."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCORE_CACHE_PATH = ROOT / "artifacts/module4_final_holdout_recovery_v1/complete_holdout_scores.csv"
PAYSIM_RAW_PATH = ROOT / "data/raw/PS_20174392719_1491204439457_log.csv"
METADATA_INDEX_PATH = ROOT / "artifacts/dashboard_metadata_index_v1"
DEMONSTRATION_FEEDBACK_DB_PATH = ROOT / "artifacts/module6_feedback/reviews.sqlite3"
FEEDBACK_DB_PATH = ROOT / "artifacts/module6_feedback/production_reviews.sqlite3"
AUTHORITATIVE_KB_PATH = ROOT / "artifacts/module5_authoritative_v1"
AUTHORITATIVE_KB_VERSION = "module5_authoritative_v1"
FROZEN_ARCHITECTURE_VERSION = "module4_stage4_rf_primary_v1"
FROZEN_THRESHOLD = 0.3494391872980995
HOLDOUT_START_STEP = 378
HOLDOUT_END_STEP = 743
DEFAULT_PAGE_SIZE = 25
MAX_PAGE_SIZE = 250

SCORE_COLUMNS = (
    "row_id", "step", "isFraud", "fraud_probability",
    "baseline_anomaly_intensity", "behavioral_anomaly_intensity",
    "rule_score_context", "alert",
)
# Fields permitted in analyst-facing score tables.  Alignment labels remain
# available to backend validation but are intentionally excluded here.
ANALYST_SCORE_DISPLAY_COLUMNS = (
    "row_id", "step", "fraud_probability", "baseline_anomaly_intensity",
    "behavioral_anomaly_intensity", "rule_score_context", "alert",
)
RAW_METADATA_COLUMNS = (
    "step", "type", "amount", "oldbalanceOrg", "newbalanceOrig",
    "oldbalanceDest", "newbalanceDest", "isFraud",
)
