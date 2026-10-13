"""Build and validate a compact, read-only PaySim holdout metadata sidecar."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from .config import HOLDOUT_END_STEP, HOLDOUT_START_STEP, RAW_METADATA_COLUMNS
from .data_access import DataValidationError, ScoreCache

METADATA_INDEX_SCHEMA_VERSION = "dashboard_metadata_index_v1"
INDEX_FILE = "holdout_metadata.parquet"
MANIFEST_FILE = "manifest.json"
INDEX_COLUMNS = ("row_id",) + RAW_METADATA_COLUMNS


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


@dataclass(frozen=True)
class MetadataIndex:
    frame: pd.DataFrame
    directory: Path
    manifest: dict


def build_metadata_index(raw_path: str | Path, score_cache: ScoreCache, destination: str | Path, *, chunksize: int = 100_000) -> MetadataIndex:
    """Stream the raw source once and atomically publish a minimal sidecar."""
    source = Path(raw_path).resolve()
    target = Path(destination).resolve()
    if target.exists():
        raise FileExistsError(f"metadata index already exists: {target}")
    if not source.is_file():
        raise FileNotFoundError(source)
    target.parent.mkdir(parents=True, exist_ok=True)
    temp_dir = Path(tempfile.mkdtemp(prefix=f".{target.name}.", dir=str(target.parent)))
    writer = None
    try:
        output = temp_dir / INDEX_FILE
        cursor = 0
        previous_step = None
        batches: list[pd.DataFrame] = []
        for chunk in pd.read_csv(source, usecols=list(RAW_METADATA_COLUMNS), chunksize=chunksize):
            if not chunk["step"].is_monotonic_increasing:
                raise DataValidationError("PaySim source ordering is not chronological")
            for value in chunk["step"].unique():
                step = int(value)
                if previous_step is not None and step < previous_step:
                    raise DataValidationError("PaySim source step ordering differs from the validated convention")
                previous_step = step
            holdout = chunk.loc[chunk["step"].between(HOLDOUT_START_STEP, HOLDOUT_END_STEP)].copy()
            if holdout.empty:
                continue
            ids = np.arange(cursor, cursor + len(holdout), dtype=np.int64)
            holdout.insert(0, "row_id", ids)
            expected = score_cache.frame.iloc[cursor:cursor + len(holdout)]
            if not np.array_equal(holdout["step"].to_numpy(dtype=np.int64), expected["step"].to_numpy(dtype=np.int64)) or not np.array_equal(holdout["isFraud"].to_numpy(dtype=np.int8), expected["isFraud"].to_numpy(dtype=np.int8)):
                raise DataValidationError("PaySim metadata does not align with the score cache")
            cursor += len(holdout)
            table = pa.Table.from_pandas(holdout[list(INDEX_COLUMNS)], preserve_index=False)
            if writer is None:
                writer = pq.ParquetWriter(output, table.schema, compression="zstd")
            writer.write_table(table)
        if writer is not None:
            writer.close()
            writer = None
        if cursor != len(score_cache.frame):
            raise DataValidationError(f"source produced {cursor} holdout rows; expected {len(score_cache.frame)}")
        parquet_hash = _sha256(output)
        manifest = {
            "schema_version": METADATA_INDEX_SCHEMA_VERSION,
            "validation_status": "passed",
            "source_path": str(source),
            "source_sha256": _sha256(source),
            "source_columns": list(RAW_METADATA_COLUMNS),
            "index_file": INDEX_FILE,
            "index_columns": list(INDEX_COLUMNS),
            "parquet_sha256": parquet_hash,
            "row_count": cursor,
            "first_row_id": 0,
            "last_row_id": cursor - 1,
            "first_step": int(score_cache.frame["step"].iloc[0]),
            "last_step": int(score_cache.frame["step"].iloc[-1]),
            "score_cache_row_count": len(score_cache.frame),
            "provenance": "Derived read-only from the validated PaySim source and frozen Module 4 score cache; labels are retained only for alignment validation.",
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
        }
        (temp_dir / MANIFEST_FILE).write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
        os.replace(temp_dir, target)
        return load_metadata_index(target, source, score_cache)
    except Exception:
        if writer is not None:
            writer.close()
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise


def load_metadata_index(directory: str | Path, raw_path: str | Path, score_cache: ScoreCache) -> MetadataIndex:
    directory = Path(directory).resolve()
    manifest_path = directory / MANIFEST_FILE
    if not manifest_path.is_file():
        raise DataValidationError(f"metadata index manifest not found: {directory}")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DataValidationError(f"invalid metadata index manifest: {exc}") from exc
    if manifest.get("schema_version") != METADATA_INDEX_SCHEMA_VERSION or manifest.get("validation_status") != "passed":
        raise DataValidationError("metadata index schema or validation status is invalid")
    source = Path(raw_path).resolve()
    if not source.is_file() or manifest.get("source_sha256") != _sha256(source):
        raise DataValidationError("metadata index source checksum does not match")
    parquet = directory / str(manifest.get("index_file", ""))
    if not parquet.is_file() or manifest.get("parquet_sha256") != _sha256(parquet):
        raise DataValidationError("metadata index parquet checksum does not match")
    try:
        frame = pd.read_parquet(parquet, columns=list(INDEX_COLUMNS))
    except Exception as exc:
        raise DataValidationError(f"unable to read metadata index: {exc}") from exc
    if len(frame) != len(score_cache.frame) or not np.array_equal(frame["row_id"].to_numpy(), np.arange(len(frame))):
        raise DataValidationError("metadata index row IDs are missing, duplicated, or out of order")
    if not np.array_equal(frame["step"].to_numpy(dtype=np.int64), score_cache.frame["step"].to_numpy(dtype=np.int64)) or not np.array_equal(frame["isFraud"].to_numpy(dtype=np.int8), score_cache.frame["isFraud"].to_numpy(dtype=np.int8)):
        raise DataValidationError("metadata index alignment labels do not match the score cache")
    if frame[list(INDEX_COLUMNS)].isna().any().any():
        raise DataValidationError("metadata index contains missing values")
    return MetadataIndex(frame=frame, directory=directory, manifest=manifest)


def lookup_index(row_ids: list[int] | tuple[int, ...], index: MetadataIndex) -> pd.DataFrame:
    requested = sorted(set(row_ids))
    if not requested:
        return index.frame.iloc[0:0].copy()
    if any(not isinstance(value, (int, np.integer)) or value < 0 or value >= len(index.frame) for value in requested):
        raise ValueError("requested row_ids are outside the metadata index")
    return index.frame.iloc[requested].copy().reset_index(drop=True)
