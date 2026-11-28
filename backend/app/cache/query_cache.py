"""
Read-Through / Write-Through Query Response Cache for PitWall AI.
Uses Upstash / Redis (REDIS_URL) when configured, falling back seamlessly
to a thread-safe 128-item in-memory TTL LRU cache.
"""

from __future__ import annotations

from collections import OrderedDict
import hashlib
import json
import logging
import os
import re
import threading
import time
from typing import Any, Dict, Optional

from backend.app.config import settings

logger = logging.getLogger("pitwall.cache.query")

_FOLLOWUP_MARKERS = (
    "him",
    "his",
    "her",
    "hers",
    "they",
    "them",
    "their",
    "that race",
    "that corner",
    "same corner",
    "same lap",
    "previous",
    "teammate",
    "instead",
    "what about",
)


def normalize_query_key(query: str, has_prior_turns: bool = False) -> Optional[str]:
    """
    Normalize a standalone natural-language query into a stable cache key.
    Returns None when the query relies on prior conversation context so
    pronoun follow-ups ('Now show his teammate') never hit stale turns.
    """
    norm = re.sub(r"\s+", " ", (query or "").strip().lower())
    if not norm:
        return None
    if has_prior_turns:
        words = set(re.findall(r"[a-z]+", norm))
        if any((" " in m and m in norm) or (" " not in m and m in words) for m in _FOLLOWUP_MARKERS):
            return None
    digest = hashlib.sha256(norm.encode("utf-8")).hexdigest()[:24]
    return f"pitwall:qcache:v1:{digest}"


class QueryResponseCache:
    """
    Thread-safe read-through/write-through cache storing verified SSE bundles
    (trace, chart, minimap, text) keyed by normalized standalone query.
    """

    def __init__(
        self,
        max_items: int = 128,
        ttl_seconds: int = 1800,
        redis_url: Optional[str] = None,
    ):
        self.max_items = max(1, max_items)
        self.ttl_seconds = max(1, ttl_seconds)
        self._lock = threading.RLock()
        self._lru: OrderedDict[str, tuple[float, Dict[str, Any]]] = OrderedDict()
        self._redis_client: Any = None
        self._init_redis(redis_url)

    def _init_redis(self, explicit_url: Optional[str]) -> None:
        url = (
            explicit_url
            if explicit_url is not None
            else (os.environ.get("REDIS_URL") or getattr(settings, "REDIS_URL", None))
        )
        if not url or not str(url).strip():
            return
        try:
            import redis

            self._redis_client = redis.from_url(
                str(url).strip(),
                decode_responses=True,
                socket_timeout=2.0,
                socket_connect_timeout=2.0,
            )
            logger.info("QueryResponseCache initialized with Redis backend.")
        except Exception as exc:
            logger.warning("Redis client init failed; using 128-item memory LRU cache: %s", exc)
            self._redis_client = None

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        """Retrieve a cached response payload if present and unexpired."""
        if not key:
            return None

        # 1. Check in-memory LRU first for sub-millisecond reads
        now = time.time()
        with self._lock:
            entry = self._lru.get(key)
            if entry is not None:
                expires_at, payload = entry
                if now <= expires_at:
                    self._lru.move_to_end(key)
                    return json.loads(json.dumps(payload))
                self._lru.pop(key, None)

        # 2. Check optional Redis backend (read-through)
        if self._redis_client is not None:
            try:
                raw = self._redis_client.get(key)
                if raw:
                    payload = json.loads(raw)
                    with self._lock:
                        self._set_memory_locked(key, payload)
                    return payload
            except Exception as exc:
                logger.warning("Redis read failed; falling back to memory cache: %s", exc)

        return None

    def _set_memory_locked(self, key: str, payload: Dict[str, Any]) -> None:
        expires_at = time.time() + self.ttl_seconds
        if key in self._lru:
            self._lru.move_to_end(key)
        self._lru[key] = (expires_at, payload)
        while len(self._lru) > self.max_items:
            self._lru.popitem(last=False)

    def set(self, key: str, payload: Dict[str, Any]) -> None:
        """Write-through payload into memory LRU and optional Redis."""
        if not key or not isinstance(payload, dict):
            return
        serialized = json.dumps(payload, default=str)
        safe_copy = json.loads(serialized)

        with self._lock:
            self._set_memory_locked(key, safe_copy)

        if self._redis_client is not None:
            try:
                self._redis_client.setex(key, self.ttl_seconds, serialized)
            except Exception as exc:
                logger.warning("Redis write failed (memory cache remains active): %s", exc)

    def clear(self) -> None:
        """Clear all in-memory cached entries (used in tests and resets)."""
        with self._lock:
            self._lru.clear()

    def size(self) -> int:
        with self._lock:
            return len(self._lru)


_query_cache_instance: Optional[QueryResponseCache] = None
_query_cache_lock = threading.Lock()


def get_query_cache() -> QueryResponseCache:
    """Return singleton QueryResponseCache instance."""
    global _query_cache_instance
    with _query_cache_lock:
        if _query_cache_instance is None:
            _query_cache_instance = QueryResponseCache(max_items=128, ttl_seconds=1800)
        return _query_cache_instance
