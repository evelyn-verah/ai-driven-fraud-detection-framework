import numpy as np
import pytest
from src.fraud_detection.pipeline import make_synthetic, evaluate, run

def test_synthetic_is_reproducible():
    assert make_synthetic(100, 9).equals(make_synthetic(100, 9))

def test_evaluation():
    y = np.array([0, 0, 1, 1])
    result = evaluate(y, np.array([.1, .2, .8, .9]))
    assert result['average_precision'] == pytest.approx(1)
    assert result['recall_at_threshold'] == pytest.approx(1)

def test_training_creates_artifacts(tmp_path):
    result = run(make_synthetic(500), tmp_path, source='synthetic')
    assert (tmp_path / 'metrics.json').exists()
    assert (tmp_path / 'logistic_regression.joblib').exists()
    assert set(result['models']) == {'logistic_regression', 'random_forest'}

def test_invalid_labels_rejected(tmp_path):
    df = make_synthetic(500)
    df.loc[0, 'is_fraud'] = 3
    with pytest.raises(ValueError): run(df, tmp_path, source='synthetic')
