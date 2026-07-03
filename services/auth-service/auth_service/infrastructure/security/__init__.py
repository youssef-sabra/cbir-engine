"""JWT signing/verification against the shared platform claim contract
(cbir_common.auth.jwt_contract) — the single source of truth for claim names,
issuer, and audience, so this signer and every verifier stay in lockstep."""

from __future__ import annotations

import time

import jwt
from cbir_common.auth.jwt_contract import (
    CLAIM_KEY_ID,
    CLAIM_PLAN_TIER,
    CLAIM_RATE_LIMIT_PER_MINUTE,
    CLAIM_SCOPES,
    JWT_ALGORITHM,
    JWT_AUDIENCE,
    JWT_ISSUER,
)

from auth_service.application.errors import AuthenticationError
from auth_service.application.ports import TokenClaims, TokenSignerPort, TokenVerifierPort


class JwtTokenSigner(TokenSignerPort):
    def __init__(self, secret: str) -> None:
        self._secret = secret

    def sign(self, claims: TokenClaims, ttl_seconds: int) -> str:
        now = int(time.time())
        payload = {
            "iss": JWT_ISSUER,
            "aud": JWT_AUDIENCE,
            "sub": claims.tenant_id,
            "iat": now,
            "exp": now + ttl_seconds,
            CLAIM_KEY_ID: claims.api_key_id,
            CLAIM_SCOPES: list(claims.scopes),
            CLAIM_PLAN_TIER: claims.plan_tier,
            CLAIM_RATE_LIMIT_PER_MINUTE: claims.rate_limit_per_minute,
        }
        return jwt.encode(payload, self._secret, algorithm=JWT_ALGORITHM)


class JwtTokenVerifier(TokenVerifierPort):
    def __init__(self, secret: str) -> None:
        self._secret = secret

    def verify(self, token: str) -> TokenClaims:
        try:
            payload = jwt.decode(
                token,
                self._secret,
                algorithms=[JWT_ALGORITHM],
                issuer=JWT_ISSUER,
                audience=JWT_AUDIENCE,
                options={"require": ["exp", "iat", "sub"]},
            )
        except jwt.PyJWTError as exc:
            raise AuthenticationError("invalid or expired access token") from exc
        return TokenClaims(
            tenant_id=payload["sub"],
            api_key_id=payload.get(CLAIM_KEY_ID, ""),
            scopes=tuple(payload.get(CLAIM_SCOPES, [])),
            plan_tier=payload.get(CLAIM_PLAN_TIER, ""),
            rate_limit_per_minute=int(payload.get(CLAIM_RATE_LIMIT_PER_MINUTE, 60)),
        )
