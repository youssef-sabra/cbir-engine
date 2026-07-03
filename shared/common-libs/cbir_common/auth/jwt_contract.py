"""The platform-wide access-token (JWT) contract.

auth-service signs tokens against these claim names; any service (or the
future API gateway) validating a token locally decodes against the same
names. Keeping the contract in one shared module is what prevents signer
and verifiers drifting apart.

Signing algorithm is HS256 with a shared secret for the local-first stack —
acceptable while every service is operated by the same party. Moving to
asymmetric keys (RS256 + JWKS) is a planned change confined to this module
and auth-service's signer when the platform grows real external trust
boundaries.
"""

from __future__ import annotations

import jwt

from cbir_common.auth.context import TenantContext

JWT_ISSUER = "cbir-auth-service"
JWT_AUDIENCE = "cbir-platform"
JWT_ALGORITHM = "HS256"

CLAIM_KEY_ID = "key_id"
CLAIM_SCOPES = "scopes"
CLAIM_PLAN_TIER = "plan_tier"
CLAIM_RATE_LIMIT_PER_MINUTE = "rate_limit_per_minute"


class InvalidAccessTokenError(Exception):
    """Raised when a bearer token fails signature, expiry, or claim checks."""


def decode_access_token(token: str, secret: str) -> TenantContext:
    """Validate a platform access token and return the tenant context.

    This is the 'gateway-level JWT validation' building block from the
    architecture plan, packaged for reuse. Note: local decoding cannot see
    the revocation list — that lives in auth-service/Redis. Services that
    need revocation awareness should validate via auth-service's
    /internal/validate endpoint instead (see fastapi_dependency.py); the
    short token TTL bounds the exposure of local-only validation.
    """
    try:
        payload = jwt.decode(
            token,
            secret,
            algorithms=[JWT_ALGORITHM],
            issuer=JWT_ISSUER,
            audience=JWT_AUDIENCE,
            options={"require": ["exp", "iat", "sub"]},
        )
    except jwt.PyJWTError as exc:
        raise InvalidAccessTokenError(str(exc)) from exc
    return TenantContext(
        tenant_id=payload["sub"],
        api_key_id=payload.get(CLAIM_KEY_ID, ""),
        scopes=list(payload.get(CLAIM_SCOPES, [])),
        plan_tier=payload.get(CLAIM_PLAN_TIER, ""),
    )
