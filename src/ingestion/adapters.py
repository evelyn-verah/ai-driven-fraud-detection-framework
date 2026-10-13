"""Dataset-specific adapters. Never combine unrelated customers across datasets."""
from pathlib import Path
import pandas as pd
from src.security.input_validation import validate_input_path, validate_paysim_frame, validate_sample_rows

PAYSIM_COLUMNS = {'step','type','amount','nameOrig','oldbalanceOrg','newbalanceOrig','nameDest','oldbalanceDest','newbalanceDest','isFraud','isFlaggedFraud'}
BANKSIM_COLUMNS = {'step','customer','age','gender','merchant','category','amount','fraud'}

def inspect_csv(path, dataset, sample_rows=100_000):
    """Read a bounded sample so full PaySim fits modest machines."""
    path = validate_input_path(path)
    sample_rows = validate_sample_rows(sample_rows)
    df=pd.read_csv(path,nrows=sample_rows)
    df.columns=df.columns.str.strip().str.replace('"','',regex=False).str.replace("'",'',regex=False)
    required=PAYSIM_COLUMNS if dataset=='paysim' else BANKSIM_COLUMNS if dataset=='banksim' else None
    if required is None: raise ValueError('dataset must be paysim or banksim')
    missing=required-set(df.columns)
    if missing: raise ValueError(f'Missing {dataset} columns: {sorted(missing)}')
    target='isFraud' if dataset=='paysim' else 'fraud'
    if df[target].isna().any() or not df[target].isin([0,1]).all(): raise ValueError('Fraud labels must be binary and non-null')
    return {'dataset':dataset,'sample_rows':int(len(df)),'sample_fraud_count':int(df[target].sum()),'sample_fraud_rate':float(df[target].mean()),'columns':list(df.columns),'note':'Sample statistics only; not full dataset statistics'}

def prepare_paysim(df):
    """Conservative transaction-time feature subset; no post-transaction balances."""
    missing=PAYSIM_COLUMNS-set(df.columns)
    if missing: raise ValueError(f'Missing PaySim columns: {sorted(missing)}')
    out=pd.DataFrame(index=df.index)
    out['step']=pd.to_numeric(df['step'],errors='coerce')
    out['type']=df['type'].astype(str)
    out['amount']=pd.to_numeric(df['amount'],errors='coerce')
    out['oldbalanceOrg']=pd.to_numeric(df['oldbalanceOrg'],errors='coerce')
    out['oldbalanceDest']=pd.to_numeric(df['oldbalanceDest'],errors='coerce')
    out['is_fraud']=pd.to_numeric(df['isFraud'],errors='coerce')
    if not out['is_fraud'].isin([0,1]).all() or out['is_fraud'].isna().any(): raise ValueError('Invalid labels')
    if out[['step','amount','oldbalanceOrg','oldbalanceDest']].isna().any().any(): raise ValueError('Null numeric features')
    if (out['amount']<0).any(): raise ValueError('Negative transaction amount')
    validate_paysim_frame(df, require_target=True, reject_extra_fields=False)
    return out
