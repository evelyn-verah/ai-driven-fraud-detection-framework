"""PaySim chronological train/validation/test benchmark; simulated data only."""
import argparse
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (average_precision_score, confusion_matrix, f1_score,
                             precision_score, recall_score, roc_auc_score)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

FEATURES = ['step', 'type', 'amount', 'oldbalanceOrg', 'oldbalanceDest']
TARGET = 'is_fraud'


def split_by_time(raw):
    """Approximate 70/15/15 transaction shares without splitting a step."""
    counts = raw.groupby('step', sort=True).size()
    if len(counts) < 6:
        raise ValueError('Need at least six unique time steps for three partitions')
    cumulative = counts.cumsum().to_numpy()
    steps = counts.index.to_numpy()
    # Boundary after a whole step; ensure at least one step per partition.
    train_end = int(np.argmin(np.abs(cumulative[:-2] - 0.70 * len(raw)))) + 1
    val_end = int(np.argmin(np.abs(cumulative[train_end:-1] - 0.85 * len(raw)))) + train_end + 1
    train = raw.loc[raw['step'] <= steps[train_end - 1]].copy()
    valid = raw.loc[(raw['step'] > steps[train_end - 1]) & (raw['step'] <= steps[val_end - 1])].copy()
    test = raw.loc[raw['step'] > steps[val_end - 1]].copy()
    for name, part in [('training', train), ('validation', valid), ('testing', test)]:
        if part.empty or part[TARGET].nunique() != 2:
            raise ValueError(f'{name} split lacks both classes; try --rows 1000000 or the full dataset')
    return train, valid, test


def scores_report(y, scores, threshold):
    pred = (scores >= threshold).astype(int)
    cm = confusion_matrix(y, pred, labels=[0, 1])
    return {
        'rows': int(len(y)),
        'fraud_count': int(np.sum(y)),
        'fraud_rate': float(np.mean(y)),
        'average_precision': float(average_precision_score(y, scores)),
        'roc_auc': float(roc_auc_score(y, scores)),
        'threshold': float(threshold),
        'precision': float(precision_score(y, pred, zero_division=0)),
        'recall': float(recall_score(y, pred, zero_division=0)),
        'f1': float(f1_score(y, pred, zero_division=0)),
        'false_positives': int(cm[0, 1]),
        'true_positives': int(cm[1, 1]),
        'confusion_matrix': cm.tolist(),
    }


def select_threshold(y, scores):
    """Choose highest validation F1; ties prefer higher threshold."""
    from sklearn.metrics import precision_recall_curve
    precision, recall, thresholds = precision_recall_curve(y, scores)
    if len(thresholds) == 0:
        return 0.5
    f1 = 2 * precision[:-1] * recall[:-1] / np.maximum(precision[:-1] + recall[:-1], 1e-12)
    return float(thresholds[int(np.flatnonzero(f1 == np.max(f1))[-1])])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--csv', default='data/raw/PS_20174392719_1491204439457_log.csv')
    parser.add_argument('--out', default='artifacts/paysim_v2')
    parser.add_argument('--rows', type=int, default=500000,
                        help='Rows to read; 0 reads full dataset (more memory intensive)')
    args = parser.parse_args()
    if args.rows < 0:
        parser.error('--rows must be zero or positive')

    dtypes = {'step': 'int32', 'type': 'category', 'amount': 'float32',
              'oldbalanceOrg': 'float32', 'oldbalanceDest': 'float32', 'isFraud': 'int8'}
    raw = pd.read_csv(args.csv, usecols=FEATURES + ['isFraud'],
                      dtype=dtypes, nrows=args.rows or None)
    raw = raw.rename(columns={'isFraud': TARGET}).dropna(subset=FEATURES + [TARGET])
    if raw.empty or not raw[TARGET].isin([0, 1]).all():
        raise ValueError('Expected nonempty dataset with binary isFraud target')
    train, valid, test = split_by_time(raw)

    preprocessor = ColumnTransformer([
        ('num', Pipeline([('impute', SimpleImputer(strategy='median')),
                          ('scale', StandardScaler())]),
         ['step', 'amount', 'oldbalanceOrg', 'oldbalanceDest']),
        ('cat', Pipeline([('impute', SimpleImputer(strategy='most_frequent')),
                          ('encode', OneHotEncoder(handle_unknown='ignore'))]), ['type'])
    ])
    models = [
        ('logistic_regression', LogisticRegression(max_iter=1500, class_weight='balanced', random_state=42)),
        ('random_forest', RandomForestClassifier(n_estimators=100, min_samples_leaf=3,
                                                max_depth=18, class_weight='balanced_subsample',
                                                random_state=42, n_jobs=2)),
    ]
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    report = {
        'dataset': 'PaySim (simulated mobile-money transactions)',
        'input_file': args.csv,
        'rows_loaded': int(len(raw)),
        'split': 'chronological by step, approximate 70/15/15 transaction counts; no shared steps',
        'threshold_selection': 'maximum validation F1; test set untouched until final evaluation',
        'splits': {name: {'rows': int(len(part)), 'fraud_count': int(part[TARGET].sum()),
                          'step_min': int(part.step.min()), 'step_max': int(part.step.max())}
                   for name, part in [('train', train), ('validation', valid), ('test', test)]},
        'features': FEATURES,
        'excluded': ['isFraud (target)', 'isFlaggedFraud', 'is_anomaly',
                     'newbalanceOrig', 'newbalanceDest', 'nameOrig', 'nameDest'],
        'models': {},
        'limitations': 'PaySim is simulated; no real-world detection or operational performance claimed.',
    }
    for name, estimator in models:
        print(f'Training {name}...', flush=True)
        model = Pipeline([('preprocess', clone(preprocessor)), ('model', estimator)])
        model.fit(train[FEATURES], train[TARGET].astype(int))
        valid_scores = model.predict_proba(valid[FEATURES])[:, 1]
        threshold = select_threshold(valid[TARGET].to_numpy(), valid_scores)
        test_scores = model.predict_proba(test[FEATURES])[:, 1]
        report['models'][name] = {
            'validation': scores_report(valid[TARGET].to_numpy(), valid_scores, threshold),
            'test': scores_report(test[TARGET].to_numpy(), test_scores, threshold),
        }
        joblib.dump(model, out / f'{name}.joblib')
    (out / 'metrics.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
