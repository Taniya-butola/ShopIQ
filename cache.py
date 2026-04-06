"""
utils/cache.py

Pluggable cache layer. Uses an in-process dict cache for development.
Swap to Redis in production by setting REDIS_URL in .env.

Usage:
    cache = CacheManager()
    cache.set("key", data, ttl=3600)
    data = cache.get("key")   # None on miss
"""

from __future__ import annotations

import json
import logging
import os
import time
from threading import Lock
from typing import Any

logger = logging.getLogger(__name__)


class _InMemoryCache:
    """Thread-safe in-memory TTL cache."""

    def __init__(self):
        self._store: dict[str, tuple[Any, float]] = {}
        self._lock = Lock()

    def get(self, key: str) -> Any | None:
        with self._lock:
            entry = self._store.get(key)
            if not entry:
                return None
            value, expires_at = entry
            if time.time() > expires_at:
                del self._store[key]
                return None
            return value

    def set(self, key: str, value: Any, ttl: int = 3600):
        with self._lock:
            self._store[key] = (value, time.time() + ttl)

    def delete(self, key: str):
        with self._lock:
            self._store.pop(key, None)

    def flush(self):
        with self._lock:
            self._store.clear()


class _RedisCache:
    """Redis-backed cache. Requires `redis` package."""

    def __init__(self, url: str):
        import redis  # type: ignore
        self._r = redis.Redis.from_url(url, decode_responses=True)
        logger.info("Connected to Redis cache.")

    def get(self, key: str) -> Any | None:
        raw = self._r.get(key)
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None

    def set(self, key: str, value: Any, ttl: int = 3600):
        self._r.setex(key, ttl, json.dumps(value))

    def delete(self, key: str):
        self._r.delete(key)

    def flush(self):
        self._r.flushdb()


class CacheManager:
    """
    Facade that auto-selects Redis (if REDIS_URL is set) or in-memory cache.
    Singleton per process.
    """

    _instance: "_InMemoryCache | _RedisCache | None" = None

    def __new__(cls):
        if cls._instance is None:
            redis_url = os.getenv("REDIS_URL")
            if redis_url:
                try:
                    cls._instance = _RedisCache(redis_url)
                except Exception as exc:
                    logger.warning(f"Redis unavailable ({exc}); falling back to in-memory cache.")
                    cls._instance = _InMemoryCache()
            else:
                cls._instance = _InMemoryCache()
        return cls._instance

    def get(self, key: str) -> Any | None:
        return self._instance.get(key)   # type: ignore[union-attr]

    def set(self, key: str, value: Any, ttl: int = 3600):
        self._instance.set(key, value, ttl)   # type: ignore[union-attr]

    def delete(self, key: str):
        self._instance.delete(key)   # type: ignore[union-attr]

    def flush(self):
        self._instance.flush()   # type: ignore[union-attr]
