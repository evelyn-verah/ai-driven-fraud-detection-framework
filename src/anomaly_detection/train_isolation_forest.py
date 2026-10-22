"""Module 3: PaySim anomaly detection using Isolation Forest."""
print("TEST: Isolation Forest script is running", flush=True)
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


FEATURES = [
    "amount",
    "oldbalanceOrg",
    "oldbalanceDest",
    "step",
]

TARGET = "isFraud"


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--csv",
        default="data/raw/PS_20174392719_1491204439457_log.csv"
    )

    parser.add_argument(
        "--rows",
        type=int,
        default=100000
    )

    parser.add_argument(
        "--out",
        default="artifacts/anomaly_detection"
    )

    args = parser.parse_args()

    print("Loading PaySim transactions...")

    df = pd.read_csv(
        args.csv,
        usecols=FEATURES + [TARGET],
        nrows=args.rows
    )

    df = df.dropna(subset=[TARGET])

    steps = np.sort(df["step"].unique())

    if len(steps) < 3:
        raise ValueError("Not enough time steps. Try more rows.")

    target_rows = int(len(df) * 0.70)

    step_counts = df.groupby("step").size().reindex(steps)
    cumulative = step_counts.cumsum().to_numpy()

    candidate_cuts = np.arange(1, len(steps))
    cut = min(
        candidate_cuts,
        key=lambda i: abs(cumulative[i - 1] - target_rows)
    )

    train = df[df["step"].isin(steps[:cut])]
    test = df[df["step"].isin(steps[cut:])]

    print(f"Training rows: {len(train):,}")
    print(f"Testing rows: {len(test):,}")

    if test[TARGET].nunique() < 2:
        raise ValueError(
            "Test set needs both fraud and legitimate transactions."
        )

    preprocessing = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
    ])

    X_train = preprocessing.fit_transform(train[FEATURES])
    X_test = preprocessing.transform(test[FEATURES])

    print("Training Isolation Forest...")

    model = IsolationForest(
        n_estimators=100,
        max_samples=256,
        contamination="auto",
        random_state=42,
        n_jobs=-1,
    )

    model.fit(X_train)

    anomaly_scores = -model.score_samples(X_test)

    y_test = test[TARGET].astype(int).to_numpy()

    review_count = min(100, len(y_test))

    ranked_indices = np.argsort(anomaly_scores)[::-1]
    selected = ranked_indices[:review_count]

    fraud_found = int(y_test[selected].sum())
    total_fraud = int(y_test.sum())

    results = {
        "dataset": "PaySim simulated mobile-money transactions",
        "method": "Isolation Forest",
        "training_type": "unsupervised",
        "rows_loaded": int(len(df)),
        "train_rows": int(len(train)),
        "test_rows": int(len(test)),
        "train_fraud_count": int(train[TARGET].sum()),
        "test_fraud_count": total_fraud,
        "train_step_max": int(train["step"].max()),
        "test_step_min": int(test["step"].min()),
        "features": FEATURES,
        "average_precision": float(
            average_precision_score(y_test, anomaly_scores)
        ),
        "roc_auc": float(
            roc_auc_score(y_test, anomaly_scores)
        ),
        "top_100_alerts": {
            "reviewed": review_count,
            "fraud_detected": fraud_found,
            "precision": float(fraud_found / review_count),
            "recall": float(fraud_found / total_fraud),
        },
        "limitations": (
            "PaySim is simulated. Anomaly scores do not establish "
            "that a transaction is fraudulent. This is an "
            "independent benchmark, not a production deployment."
        ),
    }

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    joblib.dump(
        {"preprocessor": preprocessing, "model": model},
        out / "isolation_forest.joblib"
    )

    (out / "metrics.json").write_text(
        json.dumps(results, indent=2)
    )

    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
