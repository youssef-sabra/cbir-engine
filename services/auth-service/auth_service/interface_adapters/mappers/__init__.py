"""Entity <-> ORM row mapping, kept in one testable place."""

from __future__ import annotations

from cbir_domain_kernel import TenantId

from auth_service.domain.entities import ApiKey, Tenant
from auth_service.domain.value_objects import (
    ApiKeyStatus,
    PlanTier,
    RateLimitPolicy,
    TenantStatus,
)
from auth_service.infrastructure.persistence import ApiKeyRow, TenantRow


def tenant_to_row(tenant: Tenant) -> TenantRow:
    return TenantRow(
        id=tenant.id.value,
        name=tenant.name,
        plan_tier=tenant.plan_tier.value,
        status=tenant.status.value,
        settings=tenant.settings,
        created_at=tenant.created_at,
        updated_at=tenant.updated_at,
    )


def row_to_tenant(row: TenantRow) -> Tenant:
    return Tenant(
        id=TenantId(row.id),
        name=row.name,
        plan_tier=PlanTier(row.plan_tier),
        status=TenantStatus(row.status),
        settings=dict(row.settings or {}),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def api_key_to_row(key: ApiKey) -> ApiKeyRow:
    return ApiKeyRow(
        id=key.id,
        tenant_id=key.tenant_id.value,
        name=key.name,
        secret_hash=key.secret_hash,
        scopes=list(key.scopes),
        status=key.status.value,
        rate_limit_per_minute=key.rate_limit.requests_per_minute,
        created_at=key.created_at,
        expires_at=key.expires_at,
        grace_expires_at=key.grace_expires_at,
        revoked_at=key.revoked_at,
        rotated_from_id=key.rotated_from_id,
    )


def row_to_api_key(row: ApiKeyRow) -> ApiKey:
    return ApiKey(
        id=row.id,
        tenant_id=TenantId(row.tenant_id),
        name=row.name,
        secret_hash=row.secret_hash,
        scopes=tuple(row.scopes or []),
        status=ApiKeyStatus(row.status),
        rate_limit=RateLimitPolicy(row.rate_limit_per_minute),
        created_at=row.created_at,
        expires_at=row.expires_at,
        grace_expires_at=row.grace_expires_at,
        revoked_at=row.revoked_at,
        rotated_from_id=row.rotated_from_id,
    )
