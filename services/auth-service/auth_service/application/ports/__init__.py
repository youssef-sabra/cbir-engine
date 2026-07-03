"""Abstract interfaces (beyond repositories) that use cases depend on.

Concrete implementations live in infrastructure/ and are injected by the
composition root — use cases never know whether the rate limiter is Redis
or an in-memory fake.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    limit_per_minute: int
    remaining: int
    retry_after_seconds: int


class RateLimiterPort(ABC):
    @abstractmethod
    def hit(self, bucket: str, limit_per_minute: int) -> RateLimitDecision:
        """Consume one request from `bucket`'s per-minute budget."""


class RevocationListPort(ABC):
    """Tracks revoked API key ids so already-issued bearer tokens referencing
    them die immediately instead of living until their exp claim."""

    @abstractmethod
    def revoke(self, api_key_id: str) -> None: ...

    @abstractmethod
    def is_revoked(self, api_key_id: str) -> bool: ...


@dataclass(frozen=True)
class TokenClaims:
    """What auth-service itself needs back from a verified bearer token."""

    tenant_id: str
    api_key_id: str
    scopes: tuple[str, ...]
    plan_tier: str
    rate_limit_per_minute: int


class TokenSignerPort(ABC):
    @abstractmethod
    def sign(self, claims: TokenClaims, ttl_seconds: int) -> str: ...


class TokenVerifierPort(ABC):
    @abstractmethod
    def verify(self, token: str) -> TokenClaims:
        """Raises application.errors.AuthenticationError on any failure."""


class Clock(ABC):
    @abstractmethod
    def now(self) -> datetime: ...


class SystemClock(Clock):
    def now(self) -> datetime:
        return datetime.now(timezone.utc)
