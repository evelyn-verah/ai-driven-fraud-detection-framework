import json
from pathlib import Path

import pandas as pd
import pytest

from src.dashboard.data_access import ScoreCache, DataValidationError
from src.dashboard.metadata_index import build_metadata_index, load_metadata_index, lookup_index


COLS = ["step", "type", "amount", "oldbalanceOrg", "newbalanceOrig", "oldbalanceDest", "newbalanceDest", "isFraud"]


def _fixtures(tmp_path):
    raw = tmp_path / "raw.csv"
    pd.DataFrame([
        [1, "PAYMENT", 5.0, 10.0, 5.0, 0.0, 5.0, 0],
        [378, "TRANSFER", 7.0, 10.0, 3.0, 2.0, 9.0, 0],
        [378, "CASH_OUT", 8.0, 9.0, 1.0, 2.0, 10.0, 1],
    ], columns=COLS).to_csv(raw, index=False)
    scores = pd.DataFrame({"row_id": [0, 1], "step": [378, 378], "isFraud": [0, 1], "fraud_probability": [0.1, 0.9], "baseline_anomaly_intensity": [0.1, 0.2], "behavioral_anomaly_intensity": [0.1, 0.2], "rule_score_context": [0.1, 0.2], "alert": [False, True]})
    return raw, ScoreCache(scores), tmp_path / "index"


def test_build_load_alignment_and_minimal_columns(tmp_path):
    raw, scores, target = _fixtures(tmp_path)
    before = scores.frame.copy(deep=True)
    index = build_metadata_index(raw, scores, target, chunksize=1)
    assert list(index.frame.columns) == ["row_id"] + COLS
    assert "nameOrig" not in index.frame.columns
    assert lookup_index([1, 0], index)["row_id"].tolist() == [0, 1]
    loaded = load_metadata_index(target, raw, scores)
    pd.testing.assert_frame_equal(index.frame, loaded.frame)
    pd.testing.assert_frame_equal(scores.frame, before)


def test_source_checksum_and_corruption_fail(tmp_path):
    raw, scores, target = _fixtures(tmp_path)
    build_metadata_index(raw, scores, target)
    raw.write_text(raw.read_text() + "\n", encoding="utf-8")
    with pytest.raises(DataValidationError):
        load_metadata_index(target, raw, scores)


def test_duplicate_ids_fail(tmp_path):
    raw, scores, target = _fixtures(tmp_path)
    build_metadata_index(raw, scores, target)
    parquet = target / "holdout_metadata.parquet"
    frame = pd.read_parquet(parquet)
    frame.loc[1, "row_id"] = 0
    frame.to_parquet(parquet, index=False)
    with pytest.raises(DataValidationError):
        load_metadata_index(target, raw, scores)


def test_atomic_failure_leaves_no_published_directory(tmp_path, monkeypatch):
    raw, scores, target = _fixtures(tmp_path)
    import src.dashboard.metadata_index as module
    original = module.os.replace
    def fail(src, dst):
        if Path(dst) == target:
            raise OSError("simulated publication failure")
        return original(src, dst)
    monkeypatch.setattr(module.os, "replace", fail)
    with pytest.raises(OSError):
        build_metadata_index(raw, scores, target)
    assert not target.exists()
    assert not list(target.parent.glob(f".{target.name}.*"))
