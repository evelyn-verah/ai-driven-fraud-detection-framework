"""Module 3: matched baseline and behavioral Isolation Forest experiments."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.impute import SimpleImputer
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from src.anomaly_detection.behavioral_features import (
    BEHAVIORAL_FEATURES,
    add_behavioral_features,
    summarize_activity,
)


BASE_FEATURES = ["amount", "oldbalanceOrg", "oldbalanceDest", "step"]
IDENTIFIER_FEATURES = ["nameOrig", "nameDest"]
TARGET = "isFraud"
ALERT_COUNTS = (10, 50, 100, 500)


def split_like_original_baseline(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Reproduce the original Module 3 train/test boundary exactly."""

    steps = np.sort(df["step"].unique())
    if len(steps) < 3:
        raise ValueError("Not enough time steps. Try more rows.")

    target_rows = int(len(df) * 0.70)
    step_counts = df.groupby("step", sort=True, observed=True).size().reindex(steps)
    cumulative = step_counts.cumsum().to_numpy()
    candidate_cuts = np.arange(1, len(steps))
    cut = min(
        candidate_cuts,
        key=lambda i: abs(cumulative[i - 1] - target_rows),
    )

    train = df[df["step"].isin(steps[:cut])].copy()
    test = df[df["step"].isin(steps[cut:])].copy()
    if test[TARGET].nunique() < 2:
        raise ValueError("Test set needs both fraud and legitimate transactions.")
    return train, test


def build_model() -> Pipeline:
    return Pipeline(
        [
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
            (
                "model",
                IsolationForest(
                    n_estimators=100,
                    max_samples=256,
                    contamination="auto",
                    random_state=42,
                    n_jobs=2,
                ),
            ),
        ]
    )


def alert_metrics(y_true: np.ndarray, scores: np.ndarray) -> dict[str, dict[str, float | int]]:
    """Report ranking quality and precision/recall at fixed review volumes."""

    ranked = np.argsort(scores)[::-1]
    total_fraud = int(y_true.sum())
    result: dict[str, dict[str, float | int]] = {}
    for requested in ALERT_COUNTS:
        reviewed = min(requested, len(y_true))
        selected = ranked[:reviewed]
        fraud_found = int(y_true[selected].sum())
        result[str(requested)] = {
            "requested": requested,
            "reviewed": reviewed,
            "fraud_detected": fraud_found,
            "precision": float(fraud_found / reviewed) if reviewed else 0.0,
            "recall": float(fraud_found / total_fraud) if total_fraud else 0.0,
        }
    return result


def evaluate(y_true: np.ndarray, scores: np.ndarray) -> dict:
    return {
        "average_precision": float(average_precision_score(y_true, scores)),
        "roc_auc": float(roc_auc_score(y_true, scores)),
        "alerts": alert_metrics(y_true, scores),
    }


def train_and_evaluate(
    train: pd.DataFrame,
    test: pd.DataFrame,
    features: list[str],
    out: Path,
    artifact_name: str,
) -> tuple[dict, Pipeline]:
    model = build_model()
    model.fit(train[features], train[TARGET].astype(int))
    scores = -model.named_steps["model"].score_samples(
        model[:-1].transform(test[features])
    )
    report = evaluate(test[TARGET].astype(int).to_numpy(), scores)
    report["features"] = features
    joblib.dump(model, out / artifact_name)
    return report, model


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare the original and behavioral PaySim anomaly features."
    )
    parser.add_argument(
        "--csv",
        default="data/raw/PS_20174392719_1491204439457_log.csv",
    )
    parser.add_argument("--rows", type=int, default=100000)
    parser.add_argument("--out", default="artifacts/anomaly_detection_behavioral")
    args = parser.parse_args()
    if args.rows < 1:
        parser.error("--rows must be positive")

    columns = BASE_FEATURES + IDENTIFIER_FEATURES + ["type", TARGET]
    dtypes = {
        "step": "int16",
        "type": "category",
        "amount": "float32",
        "oldbalanceOrg": "float32",
        "oldbalanceDest": "float32",
        "nameOrig": "category",
        "nameDest": "category",
        TARGET: "int8",
    }
    df = pd.read_csv(
        args.csv,
        usecols=columns,
        dtype=dtypes,
        nrows=args.rows,
    ).dropna(subset=BASE_FEATURES + IDENTIFIER_FEATURES + [TARGET])
    if df.empty or df[TARGET].nunique() < 2:
        raise ValueError("Input must contain both fraud and legitimate transactions.")

    train, test = split_like_original_baseline(df)
    print(f"Training rows: {len(train):,}", flush=True)
    print(f"Testing rows: {len(test):,}", flush=True)
    print("Building leakage-safe behavioral features...", flush=True)
    featured = add_behavioral_features(df)
    train_features = featured.loc[train.index]
    test_features = featured.loc[test.index]
    activity_analysis = summarize_activity(df, featured, train, test)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    baseline_report, _ = train_and_evaluate(
        train_features,
        test_features,
        BASE_FEATURES,
        out,
        "isolation_forest_baseline_matched.joblib",
    )
    behavioral_report, _ = train_and_evaluate(
        train_features,
        test_features,
        BASE_FEATURES + BEHAVIORAL_FEATURES,
        out,
        "isolation_forest_behavioral.joblib",
    )

    results = {
        "dataset": "PaySim simulated mobile-money transactions",
        "method": "Matched Isolation Forest comparison",
        "training_type": "unsupervised",
        "input_file": str(args.csv),
        "rows_loaded": int(len(df)),
        "split": "same 70% chronological boundary as original Module 3 baseline; no shared steps",
        "train_rows": int(len(train)),
        "test_rows": int(len(test)),
        "train_fraud_count": int(train[TARGET].sum()),
        "test_fraud_count": int(test[TARGET].sum()),
        "train_step_max": int(train["step"].max()),
        "test_step_min": int(test["step"].min()),
        "alert_counts": list(ALERT_COUNTS),
        "tuning": (
            "No tuning was performed against the final test period; the original "
            "Isolation Forest configuration was retained for both models."
        ),
        "activity_analysis": activity_analysis,
        "baseline": baseline_report,
        "behavioral": behavioral_report,
        "behavioral_feature_policy": (
            "All account and transaction-history aggregates use prior simulation steps only. "
            "Transactions within the same step do not update one another's features."
        ),
        "limitations": (
            "PaySim is simulated. Anomaly scores do not establish that a transaction is fraudulent. "
            "This is an independent benchmark, not a production deployment."
        ),
    }
    (out / "metrics.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    (out / "activity_analysis.json").write_text(
        json.dumps(activity_analysis, indent=2), encoding="utf-8"
    )
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
