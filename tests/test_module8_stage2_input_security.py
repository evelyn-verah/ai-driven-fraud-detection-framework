import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.ingestion.adapters import inspect_csv, prepare_paysim
from src.security.input_validation import (
    InputSecurityError,
    MAX_MONITORING_STEPS,
    MAX_SAMPLE_ROWS,
    SUPPORTED_PAYSIM_TYPES,
    load_secure_monitoring_config,
    validate_config_mapping,
    validate_identifier,
    validate_input_path,
    validate_monitoring_request,
    validate_output_path,
    validate_paysim_frame,
    validate_sample_rows,
    validate_text,
)


def valid_frame(rows=2):
    return pd.DataFrame({
        "step": [1] * rows,
        "type": ["TRANSFER"] * rows,
        "amount": [10.0] * rows,
        "oldbalanceOrg": [20.0] * rows,
        "oldbalanceDest": [0.0] * rows,
    })


def paysim_frame():
    frame = valid_frame()
    frame["nameOrig"] = ["C1", "C2"]
    frame["newbalanceOrig"] = [10.0, 10.0]
    frame["nameDest"] = ["C3", "C4"]
    frame["newbalanceDest"] = [10.0, 10.0]
    frame["isFraud"] = [0, 1]
    frame["isFlaggedFraud"] = [0, 0]
    return frame


def test_valid_inputs_and_baseline_ingestion(tmp_path):
    frame = paysim_frame()
    assert set(validate_paysim_frame(frame, require_target=True, reject_extra_fields=False).columns) == set(frame.columns)
    prepared = prepare_paysim(frame)
    assert len(prepared) == 2
    csv_path = tmp_path / "valid.csv"
    frame.to_csv(csv_path, index=False)
    assert inspect_csv(csv_path, "paysim")["sample_rows"] == 2
    assert SUPPORTED_PAYSIM_TYPES == {"CASH_IN", "CASH_OUT", "DEBIT", "PAYMENT", "TRANSFER"}


@pytest.mark.parametrize("column", ["step", "type", "amount", "oldbalanceOrg", "oldbalanceDest"])
def test_missing_required_fields_fail_closed(column):
    with pytest.raises(InputSecurityError, match="transaction schema"):
        validate_paysim_frame(valid_frame().drop(columns=[column]))


@pytest.mark.parametrize("value", ["not-a-number", np.nan, np.inf, -np.inf])
def test_invalid_numeric_values_fail(value):
    frame = valid_frame()
    if isinstance(value, str):
        frame["amount"] = frame["amount"].astype(object)
    frame.loc[0, "amount"] = value
    with pytest.raises((InputSecurityError, ValueError), match="amount|numeric"):
        validate_paysim_frame(frame)


def test_negative_amount_and_extreme_finite_amount():
    negative = valid_frame()
    negative.loc[0, "amount"] = -0.01
    with pytest.raises(InputSecurityError, match="amount"):
        validate_paysim_frame(negative)
    extreme = valid_frame()
    extreme.loc[0, "amount"] = 1e100
    assert validate_paysim_frame(extreme).equals(extreme)


def test_supported_types_and_unexpected_fields():
    for value in SUPPORTED_PAYSIM_TYPES:
        frame = valid_frame()
        frame.loc[0, "type"] = value
        validate_paysim_frame(frame)
    unsupported = valid_frame()
    unsupported.loc[0, "type"] = "UNKNOWN"
    with pytest.raises(InputSecurityError, match="transaction type"):
        validate_paysim_frame(unsupported)
    extra = valid_frame()
    extra["unexpected"] = 1
    with pytest.raises(InputSecurityError, match="transaction schema"):
        validate_paysim_frame(extra)


def test_oversized_strings_control_characters_and_identifiers():
    with pytest.raises(InputSecurityError):
        validate_text("x" * 4001, "reviewer label")
    with pytest.raises(InputSecurityError):
        validate_text("safe\x00value", "transaction type")
    with pytest.raises(InputSecurityError):
        validate_identifier(-1)
    with pytest.raises(InputSecurityError):
        validate_identifier(True)
    frame = valid_frame()
    frame["type"] = "TRANSFER\x00"
    with pytest.raises(InputSecurityError, match="transaction type"):
        validate_paysim_frame(frame)


def test_missing_null_and_history_identifier_values():
    frame = valid_frame()
    frame.loc[0, "type"] = None
    with pytest.raises(InputSecurityError, match="type"):
        validate_paysim_frame(frame)
    history = valid_frame()
    history["nameOrig"] = ["C1", None]
    history["nameDest"] = ["C2", "C3"]
    with pytest.raises(InputSecurityError, match="nameOrig"):
        validate_paysim_frame(history, require_history_keys=True)


def test_bounded_rows_and_paths(tmp_path):
    with pytest.raises(InputSecurityError):
        validate_sample_rows(0)
    with pytest.raises(InputSecurityError):
        validate_sample_rows(MAX_SAMPLE_ROWS + 1)
    source = tmp_path / "input.csv"
    source.write_text("step,type,amount,oldbalanceOrg,oldbalanceDest\n1,TRANSFER,1,1,0\n", encoding="utf-8")
    assert validate_input_path(source) == source
    with pytest.raises(InputSecurityError):
        validate_input_path("bad\x00path")
    assert validate_output_path(tmp_path / "output.csv").suffix == ".csv"
    with pytest.raises(InputSecurityError):
        validate_output_path(tmp_path / "output.exe")
    with pytest.raises(InputSecurityError):
        validate_output_path(tmp_path / ".." / "output.csv")


def test_monitoring_window_limits_and_malformed_configuration():
    assert validate_monitoring_request(378, 378) == (378, 378)
    assert validate_monitoring_request(378, 378 + MAX_MONITORING_STEPS - 1)[1] == 743
    with pytest.raises(InputSecurityError):
        validate_monitoring_request(378, 744)
    with pytest.raises(InputSecurityError):
        validate_monitoring_request(378, 378 + MAX_MONITORING_STEPS)
    with pytest.raises(InputSecurityError, match="configuration"):
        validate_config_mapping({})
    with pytest.raises(InputSecurityError, match="frozen_threshold"):
        validate_config_mapping({"run_id": "r", "output_dir": "out", "reference_window": {"window_id": "a", "purpose": "p", "selection_rationale": "r", "start_step": 378, "end_step": 378}, "comparison_window": {"window_id": "b", "purpose": "p", "selection_rationale": "r", "start_step": 379, "end_step": 379}, "frozen_threshold": "bad"})


def test_secure_monitoring_config_loader_rejects_unknown_fields_and_accepts_versioned_config():
    loaded = load_secure_monitoring_config(Path("configs/module7_stage5_monitoring_v1.json"))
    assert loaded.frozen_threshold == pytest.approx(0.3494391872980995)
    bad = {"run_id": "r", "output_dir": "out", "reference_window": {}, "comparison_window": {}, "unexpected": True}
    with pytest.raises(InputSecurityError, match="unsupported fields"):
        validate_config_mapping(bad)


def test_sensitive_error_messages_do_not_echo_values():
    secret = "C999999_PRIVATE_ACCOUNT"
    frame = valid_frame()
    frame["type"] = secret
    with pytest.raises(InputSecurityError) as error:
        validate_paysim_frame(frame)
    assert secret not in str(error.value)
    assert "nameOrig" not in str(error.value)
    unsafe = paysim_frame()
    unsafe["amount"] = unsafe["amount"].astype(object)
    unsafe.loc[0, "amount"] = "PRIVATE_ACCOUNT_VALUE"
    with pytest.raises(ValueError, match="Null numeric features") as conversion_error:
        prepare_paysim(unsafe)
    assert "PRIVATE_ACCOUNT_VALUE" not in str(conversion_error.value)


def test_large_collection_and_frozen_artifacts_unchanged():
    # The helper's row bound is explicit; a synthetic oversize request fails
    # before any model or artifact is touched.
    with pytest.raises(InputSecurityError):
        validate_paysim_frame(valid_frame(), maximum_rows=1)
    expected = {
        "artifacts/module7_v1_freeze_manifest.json": "8a6ce8bb8cab6c0437ac3ad63744b907dbf4688957bbf4fcbbc88eec26b280c3",
        "artifacts/module4_final_holdout_recovery_v1/complete_holdout_scores.csv": "16ab136cab8313db935fb30a6f182ddd15db7de28c9d76bdfa089345a35f9410",
        "artifacts/module5_authoritative_v1/module5_v1_freeze_manifest.json": "cba41469946685007cf475c3bfe2661076b19ca028bc883d1920f724aaa6d83c",
        "artifacts/module6_v1_freeze_manifest.json": "3d286b4f2e5fceca079c294a0be54ff80ad6286c7e1c34bbd687da4c924006fc",
    }
    for path, checksum in expected.items():
        assert hashlib.sha256(Path(path).read_bytes()).hexdigest() == checksum
