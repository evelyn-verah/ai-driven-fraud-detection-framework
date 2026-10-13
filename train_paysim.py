"""PaySim baseline training with a chronological split. Research benchmark only."""
import argparse
import json
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import average_precision_score, roc_auc_score, precision_score, recall_score, f1_score, confusion_matrix
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

FEATURES = ['step', 'type', 'amount', 'oldbalanceOrg', 'oldbalanceDest']
TARGET = 'is_fraud'

def metrics(y, scores, threshold=0.5):
    pred = (scores >= threshold).astype(int)
    return {
        'rows': len(y), 'fraud_count': int(y.sum()),
        'fraud_rate': float(y.mean()),
        'average_precision': float(average_precision_score(y, scores)),
        'roc_auc': float(roc_auc_score(y, scores)),
        'precision_at_0_5': float(precision_score(y, pred, zero_division=0)),
        'recall_at_0_5': float(recall_score(y, pred, zero_division=0)),
        'f1_at_0_5': float(f1_score(y, pred, zero_division=0)),
        'confusion_matrix': confusion_matrix(y, pred, labels=[0, 1]).tolist(),
    }

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--csv', default='data/raw/PS_20174392719_1491204439457_log.csv')
    p.add_argument('--out', default='artifacts/paysim')
    p.add_argument('--rows', type=int, default=0, help='0 means all rows; samples are for smoke tests only')
    args = p.parse_args()
    cols = FEATURES + ['isFraud']
    raw = pd.read_csv(args.csv, usecols=cols, nrows=args.rows or None)
    raw = raw.rename(columns={'isFraud': TARGET}).dropna(subset=[TARGET])
    if raw.empty or raw[TARGET].nunique() < 2:
        raise ValueError('Dataset must contain both fraud and legitimate transactions')
    # Split by unique simulation step, never split the same hour across train/test.
    steps = np.sort(raw['step'].unique())
    if len(steps) < 5:
        raise ValueError('Not enough unique time steps; try the full dataset')
    cut = int(len(steps) * 0.75)
    train_steps = set(steps[:cut])
    train = raw.loc[raw.step.isin(train_steps)]
    test = raw.loc[~raw.step.isin(train_steps)]
    if train[TARGET].nunique() < 2 or test[TARGET].nunique() < 2:
        raise ValueError('Temporal train/test partition has only one class; use the full dataset')
    preprocessor = ColumnTransformer([
        ('num', Pipeline([('impute', SimpleImputer(strategy='median')),
                          ('scale', StandardScaler())]),
         ['step', 'amount', 'oldbalanceOrg', 'oldbalanceDest']),
        ('cat', Pipeline([('impute', SimpleImputer(strategy='most_frequent')),
                          ('encode', OneHotEncoder(handle_unknown='ignore'))]), ['type'])
    ])
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    report = {
        'dataset': 'PaySim (simulated mobile-money transactions)',
        'input_file': str(args.csv),
        'split': 'chronological by step, first 75% unique steps for training',
        'train_rows': int(len(train)), 'test_rows': int(len(test)),
        'train_fraud_count': int(train[TARGET].sum()),
        'test_fraud_count': int(test[TARGET].sum()),
        'train_step_max': int(train.step.max()), 'test_step_min': int(test.step.min()),
        'features': FEATURES,
        'excluded': ['isFraud (target)', 'isFlaggedFraud', 'is_anomaly',
                     'newbalanceOrig', 'newbalanceDest', 'nameOrig', 'nameDest'],
        'models': {}
    }
    for name, estimator in [
        ('logistic_regression', LogisticRegression(max_iter=1500, class_weight='balanced', random_state=42)),
        ('random_forest', RandomForestClassifier(n_estimators=100, min_samples_leaf=3,
                                                 class_weight='balanced_subsample',
                                                 random_state=42, n_jobs=-1))
    ]:
        model = Pipeline([('preprocess', preprocessor), ('model', estimator)])
        model.fit(train[FEATURES], train[TARGET].astype(int))
        scores = model.predict_proba(test[FEATURES])[:, 1]
        report['models'][name] = metrics(test[TARGET].astype(int).to_numpy(), scores)
        joblib.dump(model, out / f'{name}.joblib')
    (out / 'metrics.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))

if __name__ == '__main__':
    main()
