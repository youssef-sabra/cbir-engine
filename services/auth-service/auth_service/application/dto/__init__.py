"""Plain data structures crossing the use-case boundary in both directions.

Decoupled from domain entities (inner) and API schemas (outer) on purpose —
see docs/CLEAN_ARCHITECTURE.md Section 3.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class CreateTenantInput:
    name: str
    plan_tier: str = "free"
    settings: dict = field(default_factory=dict)


@dataclass(frozen=True)
class TenantOutput:
    id: str
    name: str
    plan_tier: str
    status: str
    settings: dict
    created_at: datetime | None
    updated_at: datetime | None


@dataclass(frozen=True)
class IssueApiKeyInput:
    tenant_id: str
    name: str
    scopes: tuple[str, ...] | None = None  # None -> platform default scopes
    rate_limit_per_minute: int | None = None  # None -> plan-tier default
    expires_in_days: int | None = None  # None -> non-expiring


@dataclass(frozen=True)
class ApiKeyMetadataOutput:
    id: str
    tenant_id: str
    name: str
    scopes: tuple[str, ...]
    status: str
    rate_limit_per_minute: int
    created_at: datetime
    expires_at: datetime | None
    grace_expires_at: datetime | None
    revoked_at: datetime | None
    rotated_from_id: str | None


@dataclass(frozen=True)
class IssuedApiKeyOutput:
    """Returned exactly once, at issuance/rotation — the only time the full
    key string ever exists outside the caller's hands."""

    api_key: str
    metadata: ApiKeyMetadataOutput


@dataclass(frozen=True)
class RateLimitStateOutput:
    limit_per_minute: int
    remaining: int


@dataclass(frozen=True)
class AuthContextOutput:
    """The validated identity handed to the gateway/resource services."""

    tenant_id: str
    api_key_id: str
    scopes: tuple[str, ...]
    plan_tier: str
    rate_limit: RateLimitStateOutput


@dataclass(frozen=True)
class AccessTokenOutput:
    access_token: str
    token_type: str
    expires_in: int
