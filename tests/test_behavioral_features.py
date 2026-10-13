import pandas as pd
import pytest

from src.anomaly_detection.behavioral_features import (
    BEHAVIORAL_FEATURES,
    add_behavioral_features,
    summarize_activity,
)


def test_same_step_rows_do_not_see_each_other():
    df = pd.DataFrame(
        [
            {"step": 1, "type": "TRANSFER", "amount": 100.0, "nameOrig": "A", "nameDest": "B"},
            {"step": 1, "type": "TRANSFER", "amount": 900.0, "nameOrig": "A", "nameDest": "C"},
        ]
    )

    result = add_behavioral_features(df)

    assert result["sender_txn_count_prior"].tolist() == [0.0, 0.0]
    assert result["sender_avg_amount_prior"].tolist() == [0.0, 0.0]
    assert result["receiver_txn_count_prior"].tolist() == [0.0, 0.0]


def test_history_is_updated_only_after_a_step():
    df = pd.DataFrame(
        [
            {"step": 1, "type": "TRANSFER", "amount": 100.0, "nameOrig": "A", "nameDest": "B"},
            {"step": 2, "type": "TRANSFER", "amount": 300.0, "nameOrig": "A", "nameDest": "C"},
            {"step": 3, "type": "CASH_OUT", "amount": 200.0, "nameOrig": "A", "nameDest": "B"},
        ]
    )

    result = add_behavioral_features(df)

    assert result.loc[1, "sender_txn_count_prior"] == pytest.approx(1)
    assert result.loc[1, "sender_avg_amount_prior"] == pytest.approx(100)
    assert result.loc[1, "sender_same_type_count_prior"] == pytest.approx(1)
    assert result.loc[1, "sender_velocity_3_steps_prior"] == pytest.approx(1)
    assert result.loc[2, "sender_txn_count_prior"] == pytest.approx(2)
    assert result.loc[2, "sender_same_type_count_prior"] == pytest.approx(0)
    assert result.loc[2, "receiver_txn_count_prior"] == pytest.approx(1)


def test_reordering_rows_within_a_step_does_not_change_features():
    df = pd.DataFrame(
        [
            {"step": 1, "type": "TRANSFER", "amount": 100.0, "nameOrig": "A", "nameDest": "B"},
            {"step": 1, "type": "CASH_OUT", "amount": 50.0, "nameOrig": "B", "nameDest": "A"},
            {"step": 2, "type": "TRANSFER", "amount": 200.0, "nameOrig": "A", "nameDest": "B"},
        ],
        index=[10, 11, 12],
    )

    original = add_behavioral_features(df)
    reordered = add_behavioral_features(df.loc[[11, 10, 12]]).sort_index()

    pd.testing.assert_frame_equal(
        original[BEHAVIORAL_FEATURES].sort_index(),
        reordered[BEHAVIORAL_FEATURES],
    )


def test_required_columns_are_enforced():
    with pytest.raises(ValueError, match="Missing PaySim behavioral columns"):
        add_behavioral_features(pd.DataFrame({"step": [1], "amount": [1.0]}))


def test_activity_summary_uses_training_history_only():
    df = pd.DataFrame(
        [
            {"step": 1, "type": "TRANSFER", "amount": 100.0, "nameOrig": "A", "nameDest": "B"},
            {"step": 2, "type": "TRANSFER", "amount": 200.0, "nameOrig": "C", "nameDest": "B"},
            {"step": 3, "type": "TRANSFER", "amount": 300.0, "nameOrig": "A", "nameDest": "D"},
        ]
    )
    featured = add_behavioral_features(df)
    train = df.iloc[:2]
    test = df.iloc[2:]
    summary = summarize_activity(df, featured, train, test)

    assert summary["test_rows_with_prior_sender_history"] == 1
    assert summary["test_rows_with_prior_receiver_history"] == 0
    assert summary["behavioral_feature_nonzero_rates"]["sender_txn_count_prior"]["test_rows_nonzero_rate"] == 1.0
