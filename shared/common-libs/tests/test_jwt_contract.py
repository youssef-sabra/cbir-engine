import time

import jwt
import pytest

from cbir_common.auth.jwt_contract import (
    CLAIM_KEY_ID,
    CLAIM_PLAN_TIER,
    CLAIM_SCOPES,
    JWT_ALGORITHM,
    JWT_AUDIENCE,
    JWT_ISSUER,
    InvalidAccessTokenError,
    decode_access_token,
)

SECRET = "test-secret"


def _encode(claims_overrides: dict | None = None, secret: str = SECRET) -> str:
    now = int(time.time())
    claims = {
        "iss": JWT_ISSUER,
        "aud": JWT_AUDIENCE,
        "sub": "tenant-123",
        "iat": now,
        "exp": now + 60,
        CLAIM_KEY_ID: "key-456",
        CLAIM_SCOPES: ["catalog:read"],
        CLAIM_PLAN_TIER: "free",
    }
    claims.update(claims_overrides or {})
    return jwt.encode(claims, secret, algorithm=JWT_ALGORITHM)


def test_decode_valid_token_returns_context():
    context = decode_access_token(_encode(), SECRET)
    assert context.tenant_id == "tenant-123"
    assert context.api_key_id == "key-456"
    assert context.has_scope("catalog:read")
    assert not context.has_scope("catalog:write")
    assert context.plan_tier == "free"


def test_decode_rejects_wrong_secret():
    with pytest.raises(InvalidAccessTokenError):
        decode_access_token(_encode(), "wrong-secret")


def test_decode_rejects_expired_token():
    with pytest.raises(InvalidAccessTokenError):
        decode_access_token(_encode({"exp": int(time.time()) - 10}), SECRET)


def test_decode_rejects_wrong_issuer_and_audience():
    with pytest.raises(InvalidAccessTokenError):
        decode_access_token(_encode({"iss": "someone-else"}), SECRET)
    with pytest.raises(InvalidAccessTokenError):
        decode_access_token(_encode({"aud": "other-platform"}), SECRET)
