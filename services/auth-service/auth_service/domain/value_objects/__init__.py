"""Immutable, self-validating domain concepts. No identity, no side effects."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class TenantStatus(str, Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"


class PlanTier(str, Enum):
    FREE = "free"
    STANDARD = "standard"
    ENTERPRISE = "enterprise"

    @property
    def default_rate_limit_per_minute(self) -> int:
        return {
            PlanTier.FREE: 60,
            PlanTier.STANDARD: 600,
            PlanTier.ENTERPRISE: 3000,
        }[self]


class ApiKeyStatus(str, Enum):
    ACTIVE = "active"
    # A rotated-out key stays usable until its grace deadline so in-flight
    # integrations don't break the instant a rotation happens (FR4.2).
    GRACE = "grace"
    REVOKED = "revoked"


# The scopes the platform understands today. Grows as new services add
# endpoints; resource services decide which scope each endpoint requires.
KNOWN_SCOPES = frozenset({"catalog:read", "catalog:write", "search:query"})
DEFAULT_SCOPES = ("catalog:read", "catalog:write", "search:query")


class UnknownScopeError(ValueError):
    """Raised when an API key is issued with a scope the platform doesn't know."""


def validate_scopes(scopes: tuple[str, ...]) -> tuple[str, ...]:
    unknown = set(scopes) - KNOWN_SCOPES
    if unknown:
        raise UnknownScopeError(f"unknown scopes: {sorted(unknown)}; known: {sorted(KNOWN_SCOPES)}")
    if not scopes:
        raise UnknownScopeError("an API key must have at least one scope")
    return tuple(dict.fromkeys(scopes))  # de-duplicate, preserve order


@dataclass(frozen=True)
class RateLimitPolicy:
    """Requests-per-minute budget attached to an API key."""

    requests_per_minute: int

    def __post_init__(self) -> None:
        if self.requests_per_minute < 1:
            raise ValueError("rate limit must be at least 1 request per minute")
