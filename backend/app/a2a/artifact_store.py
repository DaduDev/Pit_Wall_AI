"""
Shared Thread-Safe Disk-Backed Artifact Store for PitWall AI A2A Architecture.
Keyed by UUID dataset_id with 30-minute default TTL cleanup and 200-item max cap eviction.
"""

from __future__ import annotations

from collections import OrderedDict
import datetime
import json
import logging
import math
from pathlib import Path
import threading
import time
from typing import Any
import uuid

import numpy as np
import pandas as pd

from backend.app.config import settings

logger = logging.getLogger("pitwall.a2a.artifact_store")

DEFAULT_ARTIFACT_DIR = Path("./data/artifacts")
DEFAULT_TTL_SECONDS = 1800  # 30 minutes
DEFAULT_MAX_ITEMS = 200


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
    """Thread-safe disk-backed store for large datasets with 30-min TTL & 200-item LRU/FIFO eviction."""

    def __init__(
        self,
        storage_dir: Path | str | None = None,
        max_items: int = DEFAULT_MAX_ITEMS,
        default_ttl_seconds: int = DEFAULT_TTL_SECONDS,
    ):
        resolved_dir = Path(storage_dir) if storage_dir else settings.get_artifact_cache_dir()
        self.storage_dir = resolved_dir
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.max_items = max(1, max_items)
        self.default_ttl_seconds = max(1, default_ttl_seconds)
        self._lock = threading.RLock()
        self._index: OrderedDict[str, float] = OrderedDict()
        self._seed_index()

    def _seed_index(self) -> None:
        """Index existing artifacts ordered oldest-first by modification time."""
        try:
            items = sorted(self.storage_dir.glob("*.json"), key=lambda p: p.stat().st_mtime)
            for item in items:
                self._index[item.stem] = item.stat().st_mtime
        except Exception:
            pass

    def _serialize_data(self, data: Any) -> Any:
        """Convert DataFrames or non-standard structures to JSON-serializable structures."""
        return _sanitize_for_json(data)

    def _deserialize_data(self, data: Any) -> Any:
        """Restore structures if tagged with custom type or return as-is."""
        if isinstance(data, dict) and data.get("__type__") == "dataframe":
            return pd.DataFrame(data.get("records", []))
        return data

    def _evict_if_needed_locked(self) -> int:
        """Evict expired entries and oldest entries beyond max_items. Caller holds self._lock."""
        removed = self.cleanup_expired()

        # Sync index with disk files in case files were added externally
        disk_files = sorted(self.storage_dir.glob("*.json"), key=lambda p: p.stat().st_mtime)
        while len(disk_files) > self.max_items:
            oldest = disk_files.pop(0)
            try:
                oldest.unlink()
                self._index.pop(oldest.stem, None)
                removed += 1
            except Exception as e:
                logger.warning(f"Failed evicting oldest artifact {oldest.stem}: {e}")

        while len(self._index) > self.max_items:
            oldest_id, _ = self._index.popitem(last=False)
            p = self.storage_dir / f"{oldest_id}.json"
            if p.exists():
                try:
                    p.unlink()
                    removed += 1
                except Exception:
                    pass
        return removed

    def put(
        self,
        data: Any,
        metadata: dict[str, Any] | None = None,
        dataset_id: str | None = None,
        ttl_seconds: int | None = None,
    ) -> str:
        """
        Store a dataset on disk with metadata, 30-min default TTL, and 200-item max cap eviction.
        Returns the dataset_id.
        """
        if not dataset_id:
            dataset_id = str(uuid.uuid4())

        effective_ttl = self.default_ttl_seconds if ttl_seconds is None else ttl_seconds
        now = time.time()
        expires_at = now + effective_ttl if effective_ttl > 0 else 0

        record = {
            "dataset_id": dataset_id,
            "created_at": now,
            "expires_at": expires_at,
            "metadata": _sanitize_for_json(metadata or {}),
            "data": self._serialize_data(data),
        }

        file_path = self.storage_dir / f"{dataset_id}.json"
        with self._lock:
            self.cleanup_expired()
            temp_path = self.storage_dir / f"{dataset_id}.tmp"
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(record, f, default=str, allow_nan=False)
            if temp_path.exists():
                temp_path.replace(file_path)

            if dataset_id in self._index:
                self._index.move_to_end(dataset_id)
            self._index[dataset_id] = expires_at
            self._evict_if_needed_locked()

        logger.debug(f"Artifact stored: dataset_id={dataset_id}, expires_in={effective_ttl}s")
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

            if dataset_id in self._index:
                self._index.move_to_end(dataset_id)

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
            self._index.pop(dataset_id, None)
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
                        self._index.pop(item.stem, None)
                        removed += 1
                except Exception:
                    continue
        if removed > 0:
            logger.info(f"Cleaned up {removed} expired artifacts.")
        return removed

    def count(self) -> int:
        """Return count of stored artifact files."""
        with self._lock:
            return len(list(self.storage_dir.glob("*.json")))


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
