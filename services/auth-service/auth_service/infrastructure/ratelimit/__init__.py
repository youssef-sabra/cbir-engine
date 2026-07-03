"""Redis-backed rate limiting and token revocation.

Fixed one-minute windows via INCR + EXPIRE: simple, O(1), and accurate
enough for per-key budgets (worst case a burst of up to 2x limit across a
window boundary — documented and acceptable at this stage; a sliding-window
script is a drop-in replacement inside this module if that ever matters).

Failure policy: if Redis is unreachable the limiter FAILS OPEN (requests
allowed, loudly logged) — rate limiting protects capacity, and taking the
whole platform down when the protection layer hiccups would invert that
goal (NFR9 graceful degradation). The revocation list also fails open, with
exposure bounded by the short access-token TTL.
"""

from __future__ import annotations

import logging
import time

import redis

from auth_service.application.ports import RateLimitDecision, RateLimiterPort, RevocationListPort

logger = logging.getLogger(__name__)

WINDOW_SECONDS = 60


class RedisRateLimiter(RateLimiterPort):
    def __init__(self, client: redis.Redis) -> None:
        self._redis = client

    def hit(self, bucket: str, limit_per_minute: int) -> RateLimitDecision:
        now = int(time.time())
        window_start = now - (now % WINDOW_SECONDS)
        redis_key = f"rl:{bucket}:{window_start}"
        try:
            pipe = self._redis.pipeline()
            pipe.incr(redis_key)
            pipe.expire(redis_key, WINDOW_SECONDS * 2)
            count, _ = pipe.execute()
        except redis.RedisError:
            logger.warning("rate limiter Redis unavailable; failing open", exc_info=True)
            return RateLimitDecision(
                allowed=True,
                limit_per_minute=limit_per_minute,
                remaining=limit_per_minute,
                retry_after_seconds=0,
            )
        if count > limit_per_minute:
            return RateLimitDecision(
                allowed=False,
                limit_per_minute=limit_per_minute,
                remaining=0,
                retry_after_seconds=window_start + WINDOW_SECONDS - now,
            )
        return RateLimitDecision(
            allowed=True,
            limit_per_minute=limit_per_minute,
            remaining=max(0, limit_per_minute - int(count)),
            retry_after_seconds=0,
        )


class RedisRevocationList(RevocationListPort):
    """Revoked API key ids, kept just past the max lifetime of any bearer
    token that could reference them."""

    def __init__(self, client: redis.Redis, token_ttl_seconds: int) -> None:
        self._redis = client
        self._entry_ttl = token_ttl_seconds + 60

    def revoke(self, api_key_id: str) -> None:
        try:
            self._redis.setex(f"revoked-key:{api_key_id}", self._entry_ttl, "1")
        except redis.RedisError:
            logger.error("failed to write revocation entry to Redis", exc_info=True)
            raise

    def is_revoked(self, api_key_id: str) -> bool:
        try:
            return bool(self._redis.exists(f"revoked-key:{api_key_id}"))
        except redis.RedisError:
            logger.warning("revocation list Redis unavailable; failing open", exc_info=True)
            return False
