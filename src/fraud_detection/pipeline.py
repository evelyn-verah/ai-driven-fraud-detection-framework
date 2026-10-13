"""Phase 1 reproducible baseline. No real-world validation is claimed."""
import argparse
import json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import average_precision_score, roc_auc_score, precision_score, recall_score, f1_score, confusion_matrix
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
import joblib

TARGET = 'is_fraud'
EXCLUDE = {'transaction_id', 'account_id', 'customer_id', 'timestamp', TARGET}

def make_synthetic(n=5000, seed=42):
    """Synthetic engineering fixture only. Not representative of actual fraud."""
    rng = np.random.default_rng(seed)
    amount = rng.lognormal(3.5, 1.15, n)
    hour = rng.integers(0, 24, n)
    velocity = rng.poisson(2.0, n)
    device_changed = rng.binomial(1, .12, n)
    failed_logins = rng.poisson(.3, n)
    channel = rng.choice(['app', 'web', 'ussd'], n, p=[.65,.25,.1])
    logit = -5.5 + .007 * amount + .36 * velocity + 1.1 * device_changed + .5 * failed_logins + .7 * ((hour < 5) | (hour > 22))
    prob = 1 / (1 + np.exp(-np.clip(logit, -25, 25)))
    fraud = rng.binomial(1, prob)
    return pd.DataFrame({'transaction_id': [f'SYN-{i:06d}' for i in range(n)], 'amount': amount.round(2), 'hour': hour, 'transactions_last_hour': velocity, 'device_changed': device_changed, 'failed_logins_24h': failed_logins, 'channel': channel, TARGET: fraud})

def evaluate(y, probabilities, threshold=.5):
    predicted = (probabilities >= threshold).astype(int)
    return {'rows': int(len(y)), 'fraud_count': int(np.sum(y)), 'fraud_rate': float(np.mean(y)), 'average_precision': float(average_precision_score(y, probabilities)), 'roc_auc': float(roc_auc_score(y, probabilities)), 'precision_at_threshold': float(precision_score(y, predicted, zero_division=0)), 'recall_at_threshold': float(recall_score(y, predicted, zero_division=0)), 'f1_at_threshold': float(f1_score(y, predicted, zero_division=0)), 'confusion_matrix': confusion_matrix(y, predicted).tolist(), 'threshold': threshold}

def run(df, out_dir, *, source, seed=42):
    if TARGET not in df: raise ValueError(f'Missing target column: {TARGET}')
    if df[TARGET].isna().any() or not set(df[TARGET].unique()).issubset({0, 1}): raise ValueError('is_fraud must contain only 0 and 1, without nulls')
    if df[TARGET].value_counts().min() < 5 or df[TARGET].nunique() < 2: raise ValueError('Need at least five examples in each class')
    x = df.drop(columns=[c for c in EXCLUDE if c in df], errors='ignore')
    x = x.drop(columns=[c for c in x if c.lower().startswith('unnamed:')])
    if x.empty: raise ValueError('No usable feature columns')
    unsupported = [c for c in x if not (pd.api.types.is_numeric_dtype(x[c]) or pd.api.types.is_object_dtype(x[c]) or isinstance(x[c].dtype, pd.CategoricalDtype))]
    if unsupported: raise ValueError(f'Unsupported feature dtypes: {unsupported}. Prepare features before training.')
    categorical = list(x.select_dtypes(include=['object', 'category']).columns)
    numeric = [c for c in x if c not in categorical]
    preprocessing = ColumnTransformer([
        ('num', Pipeline([('impute', SimpleImputer(strategy='median')), ('scale', StandardScaler())]), numeric),
        ('cat', Pipeline([('impute', SimpleImputer(strategy='most_frequent')), ('encode', OneHotEncoder(handle_unknown='ignore'))]), categorical)
    ])
    x_train, x_test, y_train, y_test = train_test_split(x, df[TARGET].astype(int), test_size=.25, random_state=seed, stratify=df[TARGET])
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    results = {'data_source': source, 'synthetic_data': source == 'synthetic', 'split': 'random stratified 75/25; not a temporal validation', 'seed': seed, 'target': TARGET, 'features': list(x.columns), 'models': {}}
    for name, estimator in [('logistic_regression', LogisticRegression(max_iter=1500, class_weight='balanced', random_state=seed)), ('random_forest', RandomForestClassifier(n_estimators=150, min_samples_leaf=3, class_weight='balanced_subsample', random_state=seed, n_jobs=-1))]:
        from sklearn.base import clone
        model = Pipeline([('preprocess', clone(preprocessing)), ('model', estimator)])
        model.fit(x_train, y_train)
        probabilities = model.predict_proba(x_test)[:, 1]
        results['models'][name] = evaluate(y_test.to_numpy(), probabilities)
        joblib.dump(model, out / f'{name}.joblib')
    (out / 'metrics.json').write_text(json.dumps(results, indent=2))
    return results

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--csv', help='Path to a user-supplied labeled CSV containing is_fraud (0/1)')
    p.add_argument('--out', default='artifacts')
    p.add_argument('--seed', type=int, default=42)
    p.add_argument('--synthetic-rows', type=int, default=5000)
    args = p.parse_args()
    if args.csv:
        df = pd.read_csv(args.csv)
        source = str(Path(args.csv).resolve())
    else:
        df = make_synthetic(args.synthetic_rows, args.seed)
        source = 'synthetic'
    print(json.dumps(run(df, args.out, source=source, seed=args.seed), indent=2))

if __name__ == '__main__': main()
