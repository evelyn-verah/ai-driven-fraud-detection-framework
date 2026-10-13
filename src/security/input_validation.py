"""Centralized validation for local, currently supported input surfaces.

These helpers do not change model features or scoring behavior. They reject
malformed values before existing ingestion, persistence, or monitoring code is
called and use field-level messages that do not echo transaction contents.
"""
from __future__ import annotations

import math
import os
import json
from pathlib import Path
from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np
import pandas as pd

MAX_SAMPLE_ROWS = 1_000_000
MAX_TRANSACTION_ROWS = 10_000_000
MAX_MONITORING_STEPS = 366
MAX_IDENTIFIER = 10_000_000
MAX_TEXT_LENGTH = 4_000
MAX_PATH_LENGTH = 4_096
MAX_INPUT_BYTES = 2 * 1024 * 1024 * 1024
SUPPORTED_PAYSIM_TYPES = frozenset({"CASH_IN", "CASH_OUT", "DEBIT", "PAYMENT", "TRANSFER"})
_ALLOWED_CONTROL = frozenset("\t\n\r")


class InputSecurityError(ValueError):
    """Safe, field-level validation failure for a caller-controlled value."""


def _fail(field: str, reason: str) -> InputSecurityError:
    return InputSecurityError(f"invalid {field}: {reason}")


def validate_text(value: Any, field: str, *, max_length: int = MAX_TEXT_LENGTH, allow_newlines: bool = False) -> str:
    if not isinstance(value, str):
        raise _fail(field, "text is required")
    if not value or len(value) > max_length:
        raise _fail(field, "length is outside the allowed bound")
    allowed = _ALLOWED_CONTROL if allow_newlines else frozenset("\t")
    if any(ord(char) < 32 and char not in allowed for char in value):
        raise _fail(field, "control characters are not supported")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise _fail(field, "text encoding is not supported") from exc
    return value


def validate_identifier(value: Any, *, field: str = "identifier", maximum: int = MAX_IDENTIFIER) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, np.integer)):
        raise _fail(field, "a non-negative integer is required")
    result = int(value)
    if result < 0 or result > maximum:
        raise _fail(field, "value is outside the allowed range")
    return result


def validate_sample_rows(value: Any, *, maximum: int = MAX_SAMPLE_ROWS) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, np.integer)):
        raise _fail("sample_rows", "a positive integer is required")
    result = int(value)
    if result < 1 or result > maximum:
        raise _fail("sample_rows", "value is outside the bounded inspection limit")
    return result


def validate_input_path(path: Any, *, must_exist: bool = True, maximum_bytes: int = MAX_INPUT_BYTES) -> Path:
    if not isinstance(path, (str, os.PathLike)):
        raise _fail("input path", "a filesystem path is required")
    raw = os.fspath(path)
    validate_text(raw, "input path", max_length=MAX_PATH_LENGTH)
    result = Path(raw)
    if must_exist and not result.is_file():
        raise _fail("input path", "file is unavailable")
    if result.is_file() and result.stat().st_size > maximum_bytes:
        raise _fail("input path", "file exceeds the input size limit")
    return result


def validate_output_path(path: Any, *, suffix: str = ".csv") -> Path:
    if not isinstance(path, (str, os.PathLike)):
        raise _fail("output path", "a filesystem path is required")
    raw = os.fspath(path)
    validate_text(raw, "output path", max_length=MAX_PATH_LENGTH)
    result = Path(raw)
    if result.name in {"", ".", ".."} or result.suffix.lower() != suffix.lower():
        raise _fail("output path", f"filename must use the {suffix} suffix")
    if ".." in result.parts:
        raise _fail("output path", "parent traversal is not supported")
    return result


def _finite_numeric(frame: pd.DataFrame, column: str) -> None:
    values = pd.to_numeric(frame[column], errors="coerce")
    if values.isna().any() or not np.isfinite(values.to_numpy(dtype=float)).all():
        raise _fail(column, "finite numeric values are required")


def validate_paysim_frame(
    frame: Any,
    *,
    require_history_keys: bool = False,
    require_target: bool = False,
    reject_extra_fields: bool = True,
    maximum_rows: int = MAX_TRANSACTION_ROWS,
) -> pd.DataFrame:
    """Validate a PaySim frame without mutating it or returning sensitive fields."""
    if not isinstance(frame, pd.DataFrame):
        raise _fail("transaction frame", "a pandas DataFrame is required")
    if frame.empty:
        raise _fail("transaction frame", "at least one row is required")
    if len(frame) > maximum_rows:
        raise _fail("transaction frame", "row count exceeds the bounded processing limit")
    required = {"step", "type", "amount", "oldbalanceOrg", "oldbalanceDest"}
    allowed = set(required) | {"newbalanceOrig", "newbalanceDest", "isFlaggedFraud"}
    if require_history_keys:
        required.update({"nameOrig", "nameDest"})
        allowed.update({"nameOrig", "nameDest"})
    if require_target:
        required.add("isFraud")
        allowed.add("isFraud")
    missing = sorted(required - set(frame.columns))
    if missing:
        raise _fail("transaction schema", "required fields are missing")
    if reject_extra_fields:
        extra = set(frame.columns) - allowed
        if extra:
            raise _fail("transaction schema", "unsupported fields are present")
    for column in ("step", "amount", "oldbalanceOrg", "oldbalanceDest"):
        _finite_numeric(frame, column)
    if (pd.to_numeric(frame["step"]) < 0).any() or (pd.to_numeric(frame["step"]) % 1 != 0).any():
        raise _fail("step", "a non-negative integer is required")
    if (pd.to_numeric(frame["amount"]) < 0).any():
        raise _fail("amount", "negative transaction amounts are not supported")
    if frame["type"].isna().any():
        raise _fail("type", "missing values are not supported")
    types = frame["type"].map(lambda value: validate_text(value, "transaction type", max_length=32))
    unsupported = set(types) - SUPPORTED_PAYSIM_TYPES
    if unsupported:
        raise _fail("transaction type", "category is not supported")
    for key in ("nameOrig", "nameDest"):
        if key in frame:
            if frame[key].isna().any():
                raise _fail(key, "missing values are not supported")
            frame[key].map(lambda value: validate_text(value, key, max_length=256))
    if require_target:
        target = frame["isFraud"]
        if target.isna().any() or not target.isin([0, 1]).all():
            raise _fail("isFraud", "binary non-null values are required")
    return frame


def validate_monitoring_request(start_step: Any, end_step: Any, *, allowed_start: int = 378, allowed_end: int = 743) -> tuple[int, int]:
    if any(isinstance(value, bool) or not isinstance(value, (int, np.integer)) for value in (start_step, end_step)):
        raise _fail("monitoring window", "integer step bounds are required")
    start, end = int(start_step), int(end_step)
    if start < allowed_start or end > allowed_end or start > end:
        raise _fail("monitoring window", "steps are outside the supported ordered range")
    if end - start + 1 > MAX_MONITORING_STEPS:
        raise _fail("monitoring window", "window is larger than the bounded request limit")
    return start, end


def validate_config_mapping(value: Any) -> Mapping[str, Any]:
    """Validate shape/types of a lifecycle config before its existing loader."""
    if not isinstance(value, Mapping):
        raise _fail("monitoring configuration", "a mapping is required")
    required = {"run_id", "reference_window", "comparison_window", "output_dir"}
    allowed = required | {"schema_version", "summary_windows", "score_cache_path", "metadata_sidecar_path", "feedback_enabled", "feedback_db_path", "frozen_model_version", "frozen_threshold"}
    if not required.issubset(value):
        raise _fail("monitoring configuration", "required fields are missing")
    if set(value) - allowed:
        raise _fail("monitoring configuration", "unsupported fields are present")
    validate_text(value["run_id"], "run_id", max_length=128)
    for key in ("reference_window", "comparison_window"):
        window = value[key]
        if not isinstance(window, Mapping):
            raise _fail(key, "window object is required")
        validate_text(window.get("window_id"), f"{key}.window_id", max_length=128)
        validate_text(window.get("purpose"), f"{key}.purpose", max_length=256)
        validate_text(window.get("selection_rationale"), f"{key}.selection_rationale", max_length=2000)
        validate_monitoring_request(window.get("start_step"), window.get("end_step"))
    summary_windows = value.get("summary_windows", [])
    if not isinstance(summary_windows, Sequence) or isinstance(summary_windows, (str, bytes)) or len(summary_windows) > 100:
        raise _fail("summary_windows", "collection is outside the allowed bound")
    for window in summary_windows:
        if not isinstance(window, Mapping):
            raise _fail("summary_windows", "window objects are required")
        validate_text(window.get("window_id"), "summary_windows.window_id", max_length=128)
        validate_text(window.get("purpose"), "summary_windows.purpose", max_length=256)
        validate_text(window.get("selection_rationale"), "summary_windows.selection_rationale", max_length=2000)
        validate_monitoring_request(window.get("start_step"), window.get("end_step"))
    validate_text(value["output_dir"], "output_dir", max_length=MAX_PATH_LENGTH)
    for key in ("score_cache_path", "metadata_sidecar_path", "feedback_db_path"):
        if key in value:
            validate_text(value[key], key, max_length=MAX_PATH_LENGTH)
    if "frozen_threshold" in value:
        threshold = value["frozen_threshold"]
        if isinstance(threshold, bool) or not isinstance(threshold, (int, float)) or not math.isfinite(float(threshold)) or not 0 <= float(threshold) <= 1:
            raise _fail("frozen_threshold", "finite probability is required")
    return value


def load_secure_monitoring_config(path: Any):
    """Validate a JSON configuration before delegating to the frozen loader."""
    config_path = validate_input_path(path, maximum_bytes=1_048_576)
    try:
        value = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise _fail("monitoring configuration", "file is not valid UTF-8 JSON") from exc
    validate_config_mapping(value)
    from src.monitoring.lifecycle import MonitoringLifecycleConfig
    try:
        return MonitoringLifecycleConfig.from_mapping(value)
    except (KeyError, TypeError, ValueError, FileNotFoundError, OSError) as exc:
        raise _fail("monitoring configuration", "values do not satisfy the approved lifecycle contract") from exc


__all__ = [
    "InputSecurityError", "MAX_MONITORING_STEPS", "MAX_SAMPLE_ROWS",
    "MAX_TRANSACTION_ROWS", "SUPPORTED_PAYSIM_TYPES", "validate_config_mapping",
    "load_secure_monitoring_config", "validate_identifier", "validate_input_path", "validate_monitoring_request",
    "validate_output_path", "validate_paysim_frame", "validate_sample_rows",
    "validate_text",
]
