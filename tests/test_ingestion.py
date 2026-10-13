import pandas as pd
import pytest
from src.ingestion.adapters import prepare_paysim,inspect_csv

def example():
    return pd.DataFrame([{'step':1,'type':'TRANSFER','amount':181,'nameOrig':'C1','oldbalanceOrg':181,'newbalanceOrig':0,'nameDest':'C2','oldbalanceDest':0,'newbalanceDest':181,'isFraud':1,'isFlaggedFraud':0}])

def test_paysim_output_excludes_leaky_columns():
    out=prepare_paysim(example())
    assert set(out.columns)=={'step','type','amount','oldbalanceOrg','oldbalanceDest','is_fraud'}
    assert out.iloc[0]['is_fraud']==1

def test_missing_columns():
    with pytest.raises(ValueError,match='Missing PaySim columns'): prepare_paysim(example().drop(columns=['isFraud']))

def test_bad_labels():
    df=example();df.loc[0,'isFraud']=2
    with pytest.raises(ValueError,match='Invalid labels'):prepare_paysim(df)

def test_inspection(tmp_path):
    path=tmp_path/'sample.csv';example().to_csv(path,index=False)
    report=inspect_csv(path,'paysim')
    assert report['sample_rows']==1 and report['sample_fraud_count']==1
