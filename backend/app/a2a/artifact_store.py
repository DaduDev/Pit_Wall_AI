"""
Shared Thread-Safe Disk-Backed Artifact Store for PitWall AI A2A Architecture.
Keyed by UUID dataset_id with TTL cleanup.
"""

from __future__ import annotations

import datetime
import json
import logging
import math
import os
from pathlib import Path
import threading
import time
from typing import Any
import uuid

import numpy as np
import pandas as pd

logger = logging.getLogger("pitwall.a2a.artifact_store")

DEFAULT_ARTIFACT_DIR = Path("./data/artifacts")


def _sanitize_for_json(val: Any) -> Any:
    """Recursively convert numpy, pandas, dates, and non-finite floats (NaN/Inf) into strict JSON types."""
    if val is None:
        return None
    if isinstance(val, (float, np.floating)):
        if math.isnan(val) or math.isinf(val):
            return None
        return float(val)
    if isinstance(val, (int, np.integer)):
        return int(val)
    if isinstance(val, (bool, np.bool_)):
        return bool(val)
    if isinstance(val, (datetime.datetime, datetime.date, pd.Timestamp)):
        return val.isoformat()
    if isinstance(val, np.ndarray):
        return [_sanitize_for_json(x) for x in val.tolist()]
    if isinstance(val, pd.Series):
        return [_sanitize_for_json(x) for x in val.tolist()]
    if isinstance(val, pd.DataFrame):
        return {
            "__type__": "dataframe",
            "records": _sanitize_for_json(val.to_dict(orient="records")),
            "columns": list(val.columns),
        }
    if isinstance(val, dict):
        return {str(k): _sanitize_for_json(v) for k, v in val.items()}
    if isinstance(val, (list, tuple, set)):
        return [_sanitize_for_json(x) for x in val]
    try:
        if pd.isna(val):
            return None
    except Exception:
        pass
    return val


class ArtifactStore:
    """Thread-safe disk-backed store for large datasets (telemetry, SQL results, stints)."""

    def __init__(self, storage_dir: Path | str | None = None):
        self.storage_dir = Path(storage_dir) if storage_dir else DEFAULT_ARTIFACT_DIR
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    def _serialize_data(self, data: Any) -> Any:
        """Convert DataFrames or non-standard structures to JSON-serializable structures."""
        return _sanitize_for_json(data)

    def _deserialize_data(self, data: Any) -> Any:
        """Restore structures if tagged with custom type or return as-is."""
        if isinstance(data, dict) and data.get("__type__") == "dataframe":
            return pd.DataFrame(data.get("records", []))
        return data

    def put(
        self,
        data: Any,
        metadata: dict[str, Any] | None = None,
        dataset_id: str | None = None,
        ttl_seconds: int = 3600,
    ) -> str:
        """
        Store a dataset on disk with metadata and TTL.
        Returns the dataset_id.
        """
        if not dataset_id:
            dataset_id = str(uuid.uuid4())

        now = time.time()
        expires_at = now + ttl_seconds if ttl_seconds > 0 else 0

        record = {
            "dataset_id": dataset_id,
            "created_at": now,
            "expires_at": expires_at,
            "metadata": _sanitize_for_json(metadata or {}),
            "data": self._serialize_data(data),
        }

        file_path = self.storage_dir / f"{dataset_id}.json"
        with self._lock:
            # Write to a temp file and rename for atomic write
            temp_path = self.storage_dir / f"{dataset_id}.tmp"
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(record, f, default=str, allow_nan=False)
            if temp_path.exists():
                temp_path.replace(file_path)

        logger.debug(f"Artifact stored: dataset_id={dataset_id}, expires_in={ttl_seconds}s")
        return dataset_id

    def get(self, dataset_id: str, as_dataframe: bool = False) -> dict[str, Any] | None:
        """
        Retrieve stored artifact by dataset_id.
        Returns None if not found or expired.
        """
        file_path = self.storage_dir / f"{dataset_id}.json"
        if not file_path.exists():
            return None

        with self._lock:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    record = json.load(f)
            except Exception as e:
                logger.error(f"Error reading artifact {dataset_id}: {e}")
                return None

        expires_at = record.get("expires_at", 0)
        if expires_at > 0 and time.time() > expires_at:
            logger.info(f"Artifact {dataset_id} expired, cleaning up.")
            self.delete(dataset_id)
            return None

        raw_data = record.get("data")
        if as_dataframe and isinstance(raw_data, dict) and raw_data.get("__type__") == "dataframe":
            record["data"] = self._deserialize_data(raw_data)
        elif as_dataframe and isinstance(raw_data, list):
            record["data"] = pd.DataFrame(raw_data)

        return record

    def delete(self, dataset_id: str) -> bool:
        """Delete an artifact by dataset_id."""
        file_path = self.storage_dir / f"{dataset_id}.json"
        with self._lock:
            if file_path.exists():
                try:
                    file_path.unlink()
                    return True
                except Exception as e:
                    logger.warning(f"Failed to delete artifact {dataset_id}: {e}")
        return False

    def cleanup_expired(self) -> int:
        """Scan and delete all expired artifacts. Returns number of removed files."""
        now = time.time()
        removed = 0
        with self._lock:
            for item in self.storage_dir.glob("*.json"):
                try:
                    with open(item, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    expires_at = data.get("expires_at", 0)
                    if expires_at > 0 and now > expires_at:
                        item.unlink()
                        removed += 1
                except Exception:
                    continue
        if removed > 0:
            logger.info(f"Cleaned up {removed} expired artifacts.")
        return removed


# Singleton instance
_store_instance: ArtifactStore | None = None
_store_lock = threading.Lock()


def get_artifact_store(storage_dir: Path | str | None = None) -> ArtifactStore:
    """Get or initialize singleton ArtifactStore instance."""
    global _store_instance
    with _store_lock:
        if _store_instance is None:
            _store_instance = ArtifactStore(storage_dir)
        return _store_instance
