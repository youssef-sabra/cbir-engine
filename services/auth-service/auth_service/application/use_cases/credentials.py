"""Credential validation — the hot path every platform request goes through.

Two credential shapes are accepted:
- a raw platform API key (X-API-Key header), validated against the database;
- a bearer access token previously issued by this service, validated by
  signature + the Redis revocation list, with no database round-trip.

Both paths end in the same rate-limit check, keyed by API key id, so a
tenant's budget is enforced identically however they authenticate (FR4.4).
"""

from __future__ import annotations

from auth_service.application.dto import AuthContextOutput, RateLimitStateOutput
from auth_service.application.errors import AuthenticationError, RateLimitExceededError
from auth_service.application.ports import (
    Clock,
    RateLimiterPort,
    RevocationListPort,
    TokenVerifierPort,
)
from auth_service.domain import domain_services
from auth_service.domain.domain_services import MalformedApiKeyError
from auth_service.domain.repository_interfaces import ApiKeyRepository, TenantRepository


class ValidateApiKeyCredential:
    def __init__(
        self,
        tenants: TenantRepository,
        keys: ApiKeyRepository,
        rate_limiter: RateLimiterPort,
        clock: Clock,
    ) -> None:
        self._tenants = tenants
        self._keys = keys
        self._rate_limiter = rate_limiter
        self._clock = clock

    def execute(self, presented_key: str) -> AuthContextOutput:
        try:
            key_id, secret = domain_services.parse_full_key(presented_key)
        except MalformedApiKeyError as exc:
            raise AuthenticationError(str(exc)) from exc

        key = self._keys.get(key_id)
        if key is None or not domain_services.verify_secret(secret, key.secret_hash):
            # Same message for unknown id and bad secret: don't help attackers
            # distinguish which half they got right.
            raise AuthenticationError("invalid API key")

        usable, reason = key.usability_at(self._clock.now())
        if not usable:
            raise AuthenticationError(reason)

        tenant = self._tenants.get(key.tenant_id)
        if tenant is None or not tenant.is_active():
            raise AuthenticationError("tenant account is not active")

        decision = _enforce_rate_limit(
            self._rate_limiter, str(key.id), key.rate_limit.requests_per_minute
        )
        return AuthContextOutput(
            tenant_id=str(key.tenant_id),
            api_key_id=str(key.id),
            scopes=key.scopes,
            plan_tier=tenant.plan_tier.value,
            rate_limit=decision,
        )


class ValidateAccessTokenCredential:
    def __init__(
        self,
        verifier: TokenVerifierPort,
        revocation_list: RevocationListPort,
        rate_limiter: RateLimiterPort,
    ) -> None:
        self._verifier = verifier
        self._revocation_list = revocation_list
        self._rate_limiter = rate_limiter

    def execute(self, token: str) -> AuthContextOutput:
        claims = self._verifier.verify(token)  # raises AuthenticationError
        if self._revocation_list.is_revoked(claims.api_key_id):
            raise AuthenticationError("access token's API key has been revoked")
        decision = _enforce_rate_limit(
            self._rate_limiter, claims.api_key_id, claims.rate_limit_per_minute
        )
        return AuthContextOutput(
            tenant_id=claims.tenant_id,
            api_key_id=claims.api_key_id,
            scopes=claims.scopes,
            plan_tier=claims.plan_tier,
            rate_limit=decision,
        )


def _enforce_rate_limit(
    rate_limiter: RateLimiterPort, api_key_id: str, limit_per_minute: int
) -> RateLimitStateOutput:
    decision = rate_limiter.hit(f"key:{api_key_id}", limit_per_minute)
    if not decision.allowed:
        raise RateLimitExceededError(
            limit_per_minute=decision.limit_per_minute,
            retry_after_seconds=decision.retry_after_seconds,
        )
    return RateLimitStateOutput(
        limit_per_minute=decision.limit_per_minute, remaining=decision.remaining
    )
