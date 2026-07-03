"""Redis query cache (Milestone 8): embedding cache + result cache, with
per-tenant index-version invalidation.

The tenant's index version is a Redis counter the ingestion worker bumps on
every upsert/delete. Result-cache keys embed that version, so a re-index
makes every prior key unreachable — a stale result is never served past the
next successful index write. On any Redis error the cache fails open (treated
as a miss / no-op) so a Redis outage degrades to the uncached path rather
than failing queries (NFR9).
"""

from __future__ import annotations

import json
import logging

import redis

from query_service.application.ports import QueryCachePort

logger = logging.getLogger(__name__)

# Must match the ingestion worker's RedisIndexVersionBumper key.
INDEX_VERSION_KEY = "cbir:index-version:{tenant_id}"


class RedisQueryCache(QueryCachePort):
    def __init__(self, client: redis.Redis) -> None:
        self._redis = client

    def index_version(self, tenant_id: str) -> str:
        try:
            value = self._redis.get(INDEX_VERSION_KEY.format(tenant_id=tenant_id))
            return value.decode() if value else "0"
        except redis.RedisError:
            # Unknown version -> treat as a distinct bucket so we never serve a
            # cross-version stale hit; effectively bypasses cache while down.
            logger.warning("cache index_version read failed; degrading", exc_info=True)
            return "unavailable"

    def get_results(self, key: str) -> list[dict] | None:
        return self._get_json(key)

    def set_results(self, key: str, results: list[dict], ttl_seconds: int) -> None:
        self._set_json(key, results, ttl_seconds)

    def get_embedding(self, key: str) -> list[float] | None:
        return self._get_json(key)

    def set_embedding(self, key: str, vector: list[float], ttl_seconds: int) -> None:
        self._set_json(key, vector, ttl_seconds)

    def _get_json(self, key: str):
        try:
            raw = self._redis.get(key)
            return json.loads(raw) if raw else None
        except (redis.RedisError, ValueError):
            logger.warning("cache read failed; treating as miss", exc_info=True)
            return None

    def _set_json(self, key: str, value, ttl_seconds: int) -> None:
        try:
            self._redis.setex(key, ttl_seconds, json.dumps(value))
        except redis.RedisError:
            logger.warning("cache write failed; ignoring", exc_info=True)

    def reachable(self) -> bool:
        try:
            return bool(self._redis.ping())
        except redis.RedisError:
            return False
