"""Core business objects of the auth domain. Zero external dependencies."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime

from cbir_domain_kernel import TenantId

from auth_service.domain.value_objects import (
    ApiKeyStatus,
    PlanTier,
    RateLimitPolicy,
    TenantStatus,
)


@dataclass
class Tenant:
    id: TenantId
    name: str
    plan_tier: PlanTier
    status: TenantStatus
    settings: dict = field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def is_active(self) -> bool:
        return self.status is TenantStatus.ACTIVE


@dataclass
class ApiKey:
    id: uuid.UUID
    tenant_id: TenantId
    name: str
    secret_hash: str
    scopes: tuple[str, ...]
    status: ApiKeyStatus
    rate_limit: RateLimitPolicy
    created_at: datetime
    expires_at: datetime | None = None
    grace_expires_at: datetime | None = None
    revoked_at: datetime | None = None
    rotated_from_id: uuid.UUID | None = None

    def usability_at(self, now: datetime) -> tuple[bool, str]:
        """Whether the key may authenticate at `now`, with the reason if not.

        The reason string is returned to callers in 401 responses (NFR21:
        actionable error messages), so it must stay human-readable and must
        never leak secret material.
        """
        if self.status is ApiKeyStatus.REVOKED:
            return False, "API key has been revoked"
        if self.status is ApiKeyStatus.GRACE and (
            self.grace_expires_at is None or now >= self.grace_expires_at
        ):
            return False, "API key was rotated and its grace period has ended"
        if self.expires_at is not None and now >= self.expires_at:
            return False, "API key has expired"
        return True, ""
