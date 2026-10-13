"""Validated, bounded, read-only access to frozen Module 4 outputs."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

from .config import (
    FROZEN_THRESHOLD,
    HOLDOUT_END_STEP,
    HOLDOUT_START_STEP,
    MAX_PAGE_SIZE,
    PAYSIM_RAW_PATH,
    METADATA_INDEX_PATH,
    RAW_METADATA_COLUMNS,
    SCORE_CACHE_PATH,
    SCORE_COLUMNS,
    ANALYST_SCORE_DISPLAY_COLUMNS,
)


class DataValidationError(ValueError):
    """Raised when a frozen score or source record fails integrity checks."""


@dataclass(frozen=True)
class ScoreCache:
    frame: pd.DataFrame
    validation_status: str = "passed"
    architecture_version: str = "module4_stage4_rf_primary_v1"
    threshold: float = FROZEN_THRESHOLD

    @property
    def total_transactions(self) -> int:
        return len(self.frame)

    @property
    def alert_count(self) -> int:
        return int(self.frame["alert"].sum())


def _validate_scores(frame: pd.DataFrame) -> None:
    missing = [column for column in SCORE_COLUMNS if column not in frame.columns]
    if missing:
        raise DataValidationError(f"score cache is missing required columns: {missing}")
    if frame.empty:
        raise DataValidationError("score cache is empty")
    if frame[list(SCORE_COLUMNS)].isna().any().any():
        raise DataValidationError("score cache contains missing values")
    if not pd.api.types.is_integer_dtype(frame["row_id"]):
        raise DataValidationError("row_id must be an integer column")
    if not pd.api.types.is_integer_dtype(frame["step"]):
        raise DataValidationError("step must be an integer column")
    if frame["row_id"].duplicated().any() or not np.array_equal(frame["row_id"].to_numpy(), np.arange(len(frame))):
        raise DataValidationError("row_id values must be unique and sequential from zero")
    if not frame["step"].between(HOLDOUT_START_STEP, HOLDOUT_END_STEP).all():
        raise DataValidationError("score cache contains steps outside the frozen holdout")
    if not frame["isFraud"].isin([0, 1]).all():
        raise DataValidationError("isFraud must contain only 0/1 values")
    score_columns = ["fraud_probability", "baseline_anomaly_intensity", "behavioral_anomaly_intensity", "rule_score_context"]
    values = frame[score_columns].to_numpy(dtype=float)
    if not np.isfinite(values).all() or ((values < 0) | (values > 1)).any():
        raise DataValidationError("score columns must be finite values in [0, 1]")
    expected_alert = frame["fraud_probability"].to_numpy(dtype=float) >= FROZEN_THRESHOLD
    if not np.array_equal(frame["alert"].to_numpy(dtype=bool), expected_alert):
        raise DataValidationError("alert decisions do not match the frozen threshold")
    if not frame["step"].is_monotonic_increasing:
        raise DataValidationError("score cache steps must be chronologically ordered")


@lru_cache(maxsize=2)
def _load_cached(path_string: str, modified_ns: int) -> ScoreCache:
    path = Path(path_string)
    if not path.is_file():
        raise FileNotFoundError(f"score cache not found: {path}")
    try:
        header = pd.read_csv(path, nrows=0)
    except (OSError, ValueError) as exc:
        raise DataValidationError(f"unable to read score-cache header: {exc}") from exc
    missing = [column for column in SCORE_COLUMNS if column not in header.columns]
    if missing:
        raise DataValidationError(f"score cache is missing required columns: {missing}")
    dtype = {"row_id": "int64", "step": "int16", "isFraud": "int8", "alert": "boolean"}
    for column in SCORE_COLUMNS[3:7]:
        dtype[column] = "float64"
    try:
        frame = pd.read_csv(path, usecols=list(SCORE_COLUMNS), dtype=dtype)
    except (OSError, ValueError, TypeError) as exc:
        raise DataValidationError(f"unable to read score cache: {exc}") from exc
    _validate_scores(frame)
    return ScoreCache(frame=frame)


def load_score_cache(path: str | Path = SCORE_CACHE_PATH) -> ScoreCache:
    """Load and validate the immutable score cache with bounded column selection."""
    resolved = Path(path)
    if not resolved.is_file():
        raise FileNotFoundError(f"score cache not found: {resolved}")
    return _load_cached(str(resolved.resolve()), resolved.stat().st_mtime_ns)


def filter_scores(
    frame: pd.DataFrame,
    *,
    row_id_min: int | None = None,
    row_id_max: int | None = None,
    step_min: int | None = None,
    step_max: int | None = None,
    alert: bool | None = None,
    probability_min: float | None = None,
    probability_max: float | None = None,
) -> pd.DataFrame:
    """Filter without changing row order; callers receive a new view."""
    required = set(SCORE_COLUMNS)
    if not required.issubset(frame.columns):
        raise DataValidationError("filter input is not a score frame")
    mask = np.ones(len(frame), dtype=bool)
    if row_id_min is not None: mask &= frame["row_id"].to_numpy() >= row_id_min
    if row_id_max is not None: mask &= frame["row_id"].to_numpy() <= row_id_max
    if step_min is not None: mask &= frame["step"].to_numpy() >= step_min
    if step_max is not None: mask &= frame["step"].to_numpy() <= step_max
    if alert is not None: mask &= frame["alert"].to_numpy(dtype=bool) == alert
    if probability_min is not None: mask &= frame["fraud_probability"].to_numpy() >= probability_min
    if probability_max is not None: mask &= frame["fraud_probability"].to_numpy() <= probability_max
    result = frame.loc[mask]
    return result.sort_values("row_id", kind="stable").reset_index(drop=True)


def paginate_scores(frame: pd.DataFrame, *, page: int = 1, page_size: int = 25) -> pd.DataFrame:
    if not isinstance(page, int) or isinstance(page, bool) or page < 1:
        raise ValueError("page must be a positive integer")
    if not isinstance(page_size, int) or isinstance(page_size, bool) or not 1 <= page_size <= MAX_PAGE_SIZE:
        raise ValueError(f"page_size must be between 1 and {MAX_PAGE_SIZE}")
    ordered = frame.sort_values("row_id", kind="stable")
    start = (page - 1) * page_size
    return ordered.iloc[start:start + page_size].reset_index(drop=True)


def analyst_display_scores(frame: pd.DataFrame) -> pd.DataFrame:
    """Project validated scores to fields safe for analyst-facing tables."""
    if not set(ANALYST_SCORE_DISPLAY_COLUMNS).issubset(frame.columns):
        raise DataValidationError("analyst display input is missing required score fields")
    return frame.loc[:, list(ANALYST_SCORE_DISPLAY_COLUMNS)].copy()


def overview_aggregations(frame: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Build compact chart tables from frozen scores without rescoring."""
    required = set(SCORE_COLUMNS)
    if not required.issubset(frame.columns):
        raise DataValidationError("overview input is not a score frame")
    probability_bins = np.linspace(0.0, 1.0, 11)
    probability_labels = [f"{left:.1f}–{right:.1f}" for left, right in zip(probability_bins[:-1], probability_bins[1:])]
    probability = pd.cut(frame["fraud_probability"], bins=probability_bins, labels=probability_labels, include_lowest=True)
    probability_distribution = probability.value_counts(sort=False).rename("transactions").reset_index()
    probability_distribution.columns = ["probability_band", "transactions"]
    alerts_by_step = frame.groupby("step", sort=True, observed=True)["alert"].agg(alerts="sum", transactions="size").reset_index()
    alerts_by_step["alert_rate"] = alerts_by_step["alerts"] / alerts_by_step["transactions"]
    anomaly_distribution = frame[["baseline_anomaly_intensity", "behavioral_anomaly_intensity"]].rename(
        columns={"baseline_anomaly_intensity": "Baseline", "behavioral_anomaly_intensity": "Behavioral"}
    )
    anomaly_distribution = anomaly_distribution.assign(
        band=pd.cut(np.maximum(anomaly_distribution["Baseline"], anomaly_distribution["Behavioral"]), bins=10, include_lowest=True)
    )
    anomaly_distribution = anomaly_distribution.groupby("band", observed=True)[["Baseline", "Behavioral"]].mean().reset_index()
    anomaly_distribution["band"] = anomaly_distribution["band"].astype(str)
    return {
        "probability_distribution": probability_distribution,
        "alerts_by_step": alerts_by_step,
        "anomaly_distribution": anomaly_distribution,
    }


def lookup_metadata(
    row_ids: Iterable[int],
    score_cache: ScoreCache,
    *,
    raw_path: str | Path = PAYSIM_RAW_PATH,
    chunksize: int = 100_000,
    metadata_index=None,
    use_metadata_index: bool = True,
) -> pd.DataFrame:
    """Return selected PaySim rows after chronological score alignment checks."""
    requested = tuple(sorted(set(row_ids)))
    if not requested:
        return pd.DataFrame(columns=("row_id",) + RAW_METADATA_COLUMNS)
    if any(not isinstance(value, (int, np.integer)) or value < 0 or value >= len(score_cache.frame) for value in requested):
        raise ValueError("requested row_ids are outside the score cache")
    if metadata_index is None and use_metadata_index and METADATA_INDEX_PATH.is_dir() and Path(raw_path).resolve() == PAYSIM_RAW_PATH.resolve():
        from .metadata_index import load_metadata_index
        metadata_index = load_metadata_index(METADATA_INDEX_PATH, raw_path, score_cache)
    if metadata_index is not None:
        from .metadata_index import lookup_index
        return lookup_index(requested, metadata_index)
    source = Path(raw_path)
    if not source.is_file():
        raise FileNotFoundError(f"PaySim source not found: {source}")
    expected = score_cache.frame.set_index("row_id").loc[list(requested), ["step", "isFraud"]]
    found: list[pd.DataFrame] = []
    holdout_cursor = 0
    previous_step: int | None = None
    for chunk in pd.read_csv(source, usecols=list(RAW_METADATA_COLUMNS), chunksize=chunksize):
        if not chunk["step"].is_monotonic_increasing:
            raise DataValidationError("PaySim source ordering is not chronological")
        for step in chunk["step"].unique():
            step_value = int(step)
            if previous_step is not None and step_value < previous_step:
                raise DataValidationError("PaySim source step ordering differs from the validated convention")
            previous_step = step_value
        holdout_mask = chunk["step"].between(HOLDOUT_START_STEP, HOLDOUT_END_STEP)
        if not holdout_mask.any():
            continue
        holdout = chunk.loc[holdout_mask].copy()
        ids = np.arange(holdout_cursor, holdout_cursor + len(holdout), dtype=np.int64)
        holdout_cursor += len(holdout)
        wanted = np.isin(ids, requested)
        if wanted.any():
            selected = holdout.loc[wanted].copy()
            selected.insert(0, "row_id", ids[wanted])
            observed = selected.set_index("row_id")[["step", "isFraud"]]
            expected_rows = expected.loc[observed.index]
            if not np.array_equal(observed["step"].to_numpy(dtype=np.int64), expected_rows["step"].to_numpy(dtype=np.int64)) or not np.array_equal(observed["isFraud"].to_numpy(dtype=np.int8), expected_rows["isFraud"].to_numpy(dtype=np.int8)):
                raise DataValidationError("PaySim metadata does not align with the score cache")
            found.append(selected)
        if holdout_cursor > requested[-1] and holdout_cursor >= len(score_cache.frame):
            break
    if holdout_cursor < len(score_cache.frame):
        raise DataValidationError("PaySim source ended before the complete holdout alignment was established")
    result = pd.concat(found, ignore_index=True) if found else pd.DataFrame(columns=("row_id",) + RAW_METADATA_COLUMNS)
    if len(result) != len(requested) or set(result["row_id"]) != set(requested):
        raise DataValidationError("one or more requested row_ids were not found in PaySim source")
    return result.sort_values("row_id", kind="stable").reset_index(drop=True)
