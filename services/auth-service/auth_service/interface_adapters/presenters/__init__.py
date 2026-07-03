"""Translate use-case output DTOs into HTTP response schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from auth_service.application.dto import (
    AccessTokenOutput,
    ApiKeyMetadataOutput,
    AuthContextOutput,
    IssuedApiKeyOutput,
    TenantOutput,
)


class TenantResponse(BaseModel):
    id: str
    name: str
    plan_tier: str
    status: str
    settings: dict
    created_at: datetime | None
    updated_at: datetime | None


class ApiKeyMetadataResponse(BaseModel):
    id: str
    tenant_id: str
    name: str
    scopes: list[str]
    status: str
    rate_limit_per_minute: int
    created_at: datetime
    expires_at: datetime | None
    grace_expires_at: datetime | None
    revoked_at: datetime | None
    rotated_from_id: str | None


class IssuedApiKeyResponse(BaseModel):
    api_key: str
    note: str = "Store this key now — it is shown only once and only its hash is kept server-side."
    metadata: ApiKeyMetadataResponse


class RateLimitStateResponse(BaseModel):
    limit_per_minute: int
    remaining: int


class ValidatedContextResponse(BaseModel):
    """Shape consumed by cbir_common.auth.TenantContext — must stay a superset
    of that contract."""

    tenant_id: str
    api_key_id: str
    scopes: list[str]
    plan_tier: str
    rate_limit: RateLimitStateResponse


class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: str
    expires_in: int


def present_tenant(dto: TenantOutput) -> TenantResponse:
    return TenantResponse(**dto.__dict__)


def present_key_metadata(dto: ApiKeyMetadataOutput) -> ApiKeyMetadataResponse:
    data = dto.__dict__ | {"scopes": list(dto.scopes)}
    return ApiKeyMetadataResponse(**data)


def present_issued_key(dto: IssuedApiKeyOutput) -> IssuedApiKeyResponse:
    return IssuedApiKeyResponse(api_key=dto.api_key, metadata=present_key_metadata(dto.metadata))


def present_auth_context(dto: AuthContextOutput) -> ValidatedContextResponse:
    return ValidatedContextResponse(
        tenant_id=dto.tenant_id,
        api_key_id=dto.api_key_id,
        scopes=list(dto.scopes),
        plan_tier=dto.plan_tier,
        rate_limit=RateLimitStateResponse(
            limit_per_minute=dto.rate_limit.limit_per_minute,
            remaining=dto.rate_limit.remaining,
        ),
    )


def present_access_token(dto: AccessTokenOutput) -> AccessTokenResponse:
    return AccessTokenResponse(**dto.__dict__)
