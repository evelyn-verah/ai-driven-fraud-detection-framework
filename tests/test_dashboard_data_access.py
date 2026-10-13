import pandas as pd
import pytest

from src.dashboard.data_access import DataValidationError, ScoreCache, analyst_display_scores, filter_scores, load_score_cache, lookup_metadata, overview_aggregations, paginate_scores


def test_real_score_cache_validates_without_rescoring():
    cache = load_score_cache()
    assert cache.total_transactions == 955744
    assert cache.frame.row_id.iloc[0] == 0
    assert cache.frame.row_id.iloc[-1] == 955743
    assert cache.alert_count == int((cache.frame.fraud_probability >= cache.threshold).sum())


def test_filtering_and_stable_pagination():
    cache = load_score_cache()
    filtered = filter_scores(cache.frame, step_min=378, step_max=378, alert=False, probability_max=0.2)
    assert filtered.row_id.is_monotonic_increasing
    page = paginate_scores(filtered, page=2, page_size=5)
    assert len(page) <= 5
    if len(page):
        assert page.row_id.iloc[0] > filtered.row_id.iloc[0]


def test_analyst_display_projection_excludes_internal_labels_and_identifiers():
    cache = _fixture_cache()
    displayed = analyst_display_scores(cache.frame)
    assert "isFraud" not in displayed.columns
    assert "nameOrig" not in displayed.columns
    assert "nameDest" not in displayed.columns
    assert displayed.row_id.tolist() == [0, 1]
    assert displayed.alert.tolist() == [False, True]


def test_missing_columns_and_alert_mutation_fail(tmp_path):
    cache = load_score_cache()
    missing = tmp_path / "missing.csv"
    cache.frame.drop(columns=["alert"]).head(2).to_csv(missing, index=False)
    with pytest.raises(DataValidationError, match="missing required"):
        load_score_cache(missing)
    invalid = tmp_path / "invalid.csv"
    altered = cache.frame.head(2).copy()
    altered.loc[0, "alert"] = not bool(altered.loc[0, "alert"])
    altered.to_csv(invalid, index=False)
    with pytest.raises(DataValidationError, match="alert"):
        load_score_cache(invalid)


def _fixture_cache() -> ScoreCache:
    frame = pd.DataFrame({
        "row_id": [0, 1], "step": [378, 379], "isFraud": [0, 1],
        "fraud_probability": [0.1, 0.9], "baseline_anomaly_intensity": [0.4, 0.5],
        "behavioral_anomaly_intensity": [0.4, 0.6], "rule_score_context": [0.0, 1.0],
        "alert": [False, True],
    })
    return ScoreCache(frame=frame)


def _write_raw(path, *, fraud_second=1):
    pd.DataFrame([
        {"step": 377, "type": "PAYMENT", "amount": 1, "nameOrig": "a", "oldbalanceOrg": 1, "newbalanceOrig": 0, "nameDest": "b", "oldbalanceDest": 0, "newbalanceDest": 1, "isFraud": 0, "isFlaggedFraud": 0},
        {"step": 378, "type": "TRANSFER", "amount": 2, "nameOrig": "c", "oldbalanceOrg": 2, "newbalanceOrig": 0, "nameDest": "d", "oldbalanceDest": 0, "newbalanceDest": 2, "isFraud": 0, "isFlaggedFraud": 0},
        {"step": 379, "type": "CASH_OUT", "amount": 3, "nameOrig": "e", "oldbalanceOrg": 3, "newbalanceOrig": 0, "nameDest": "f", "oldbalanceDest": 0, "newbalanceDest": 3, "isFraud": fraud_second, "isFlaggedFraud": 0},
    ]).to_csv(path, index=False)


def test_metadata_lookup_uses_holdout_relative_row_ids(tmp_path):
    raw = tmp_path / "raw.csv"
    _write_raw(raw)
    result = lookup_metadata([1], _fixture_cache(), raw_path=raw)
    assert result.loc[0, "row_id"] == 1
    assert result.loc[0, "step"] == 379
    assert result.loc[0, "type"] == "CASH_OUT"


def test_metadata_alignment_and_missing_source_fail(tmp_path):
    raw = tmp_path / "raw.csv"
    _write_raw(raw, fraud_second=0)
    with pytest.raises(DataValidationError, match="align"):
        lookup_metadata([1], _fixture_cache(), raw_path=raw)
    with pytest.raises(FileNotFoundError):
        lookup_metadata([0], _fixture_cache(), raw_path=tmp_path / "absent.csv")


def test_pagination_arguments_are_validated():
    cache = load_score_cache()
    with pytest.raises(ValueError):
        paginate_scores(cache.frame, page=0)
    with pytest.raises(ValueError):
        paginate_scores(cache.frame, page_size=0)


def test_overview_aggregations_cover_all_rows_and_steps():
    cache = load_score_cache()
    charts = overview_aggregations(cache.frame)
    assert int(charts["probability_distribution"]["transactions"].sum()) == len(cache.frame)
    assert len(charts["alerts_by_step"]) == 366
    assert int(charts["alerts_by_step"]["transactions"].sum()) == len(cache.frame)
    assert set(charts["anomaly_distribution"].columns) == {"band", "Baseline", "Behavioral"}
