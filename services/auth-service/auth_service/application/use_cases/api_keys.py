"""API key lifecycle: issue, rotate (with grace period), revoke, list.

Direct expression of FR4.2 (issuance, rotation, scoped permissions) and
FR4.4 (configurable per-key rate limits).
"""

from __future__ import annotations

import uuid
from datetime import timedelta

from cbir_domain_kernel import InvalidTenantIdError, TenantId

from auth_service.application.dto import (
    ApiKeyMetadataOutput,
    IssueApiKeyInput,
    IssuedApiKeyOutput,
)
from auth_service.application.errors import ApiKeyNotFoundError, TenantNotFoundError
from auth_service.application.ports import Clock, RevocationListPort
from auth_service.domain import domain_services
from auth_service.domain.entities import ApiKey
from auth_service.domain.repository_interfaces import ApiKeyRepository, TenantRepository
from auth_service.domain.value_objects import (
    DEFAULT_SCOPES,
    ApiKeyStatus,
    RateLimitPolicy,
    validate_scopes,
)


def present_key_metadata(key: ApiKey) -> ApiKeyMetadataOutput:
    return ApiKeyMetadataOutput(
        id=str(key.id),
        tenant_id=str(key.tenant_id),
        name=key.name,
        scopes=key.scopes,
        status=key.status.value,
        rate_limit_per_minute=key.rate_limit.requests_per_minute,
        created_at=key.created_at,
        expires_at=key.expires_at,
        grace_expires_at=key.grace_expires_at,
        revoked_at=key.revoked_at,
        rotated_from_id=str(key.rotated_from_id) if key.rotated_from_id else None,
    )


class IssueApiKey:
    def __init__(self, tenants: TenantRepository, keys: ApiKeyRepository, clock: Clock) -> None:
        self._tenants = tenants
        self._keys = keys
        self._clock = clock

    def execute(self, data: IssueApiKeyInput) -> IssuedApiKeyOutput:
        try:
            tenant_id = TenantId.parse(data.tenant_id)
        except InvalidTenantIdError as exc:
            raise TenantNotFoundError(f"no tenant with id '{data.tenant_id}'") from exc
        tenant = self._tenants.get(tenant_id)
        if tenant is None:
            raise TenantNotFoundError(f"no tenant with id '{data.tenant_id}'")

        scopes = validate_scopes(tuple(data.scopes) if data.scopes else DEFAULT_SCOPES)
        rate_limit = RateLimitPolicy(
            data.rate_limit_per_minute
            if data.rate_limit_per_minute is not None
            else tenant.plan_tier.default_rate_limit_per_minute
        )
        now = self._clock.now()
        issued = domain_services.issue_secret()
        key = ApiKey(
            id=issued.key_id,
            tenant_id=tenant_id,
            name=data.name.strip() or "default",
            secret_hash=issued.secret_hash,
            scopes=scopes,
            status=ApiKeyStatus.ACTIVE,
            rate_limit=rate_limit,
            created_at=now,
            expires_at=(
                now + timedelta(days=data.expires_in_days)
                if data.expires_in_days is not None
                else None
            ),
        )
        self._keys.add(key)
        return IssuedApiKeyOutput(api_key=issued.full_key, metadata=present_key_metadata(key))


class RotateApiKey:
    """Issue a replacement key; the old key stays usable for a grace period
    so integrations can switch over without downtime, then dies."""

    def __init__(
        self,
        keys: ApiKeyRepository,
        clock: Clock,
        grace_seconds: int,
    ) -> None:
        self._keys = keys
        self._clock = clock
        self._grace_seconds = grace_seconds

    def execute(self, key_id: str) -> IssuedApiKeyOutput:
        old = _get_key_or_raise(self._keys, key_id)
        if old.status is not ApiKeyStatus.ACTIVE:
            raise ApiKeyNotFoundError(f"API key '{key_id}' is not active and cannot be rotated")
        now = self._clock.now()
        old.status = ApiKeyStatus.GRACE
        old.grace_expires_at = now + timedelta(seconds=self._grace_seconds)
        self._keys.update(old)

        issued = domain_services.issue_secret()
        replacement = ApiKey(
            id=issued.key_id,
            tenant_id=old.tenant_id,
            name=old.name,
            secret_hash=issued.secret_hash,
            scopes=old.scopes,
            status=ApiKeyStatus.ACTIVE,
            rate_limit=old.rate_limit,
            created_at=now,
            expires_at=old.expires_at,
            rotated_from_id=old.id,
        )
        self._keys.add(replacement)
        return IssuedApiKeyOutput(
            api_key=issued.full_key, metadata=present_key_metadata(replacement)
        )


class RevokeApiKey:
    def __init__(
        self,
        keys: ApiKeyRepository,
        revocation_list: RevocationListPort,
        clock: Clock,
    ) -> None:
        self._keys = keys
        self._revocation_list = revocation_list
        self._clock = clock

    def execute(self, key_id: str) -> ApiKeyMetadataOutput:
        key = _get_key_or_raise(self._keys, key_id)
        key.status = ApiKeyStatus.REVOKED
        key.revoked_at = self._clock.now()
        self._keys.update(key)
        # Kill already-issued bearer tokens referencing this key immediately,
        # rather than letting them live until their exp claim.
        self._revocation_list.revoke(str(key.id))
        return present_key_metadata(key)


class ListApiKeys:
    def __init__(self, keys: ApiKeyRepository) -> None:
        self._keys = keys

    def execute(self, tenant_id: str) -> list[ApiKeyMetadataOutput]:
        try:
            parsed = TenantId.parse(tenant_id)
        except InvalidTenantIdError as exc:
            raise TenantNotFoundError(f"no tenant with id '{tenant_id}'") from exc
        return [present_key_metadata(k) for k in self._keys.list_for_tenant(parsed)]


def _get_key_or_raise(keys: ApiKeyRepository, key_id: str):
    try:
        parsed = uuid.UUID(key_id)
    except ValueError as exc:
        raise ApiKeyNotFoundError(f"no API key with id '{key_id}'") from exc
    key = keys.get(parsed)
    if key is None:
        raise ApiKeyNotFoundError(f"no API key with id '{key_id}'")
    return key
