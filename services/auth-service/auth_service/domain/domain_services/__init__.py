"""Business rules that operate across entities or define domain-wide policy.

ApiKeySecretScheme is the single authority on what an API key *is* as a
string, how its secret is hashed at rest, and how presented keys are
verified. Keys are hashed with SHA-256: the secret is 256 bits of CSPRNG
output, so key-stretching (bcrypt/argon2) adds cost without adding security,
and validation sits on the hot path of every request.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import uuid
from dataclasses import dataclass

KEY_PREFIX = "cbir"


class MalformedApiKeyError(ValueError):
    """Raised when a presented credential is not shaped like a platform API key."""


@dataclass(frozen=True)
class IssuedSecret:
    """The one-time result of generating a key: the full key string is shown
    to the caller exactly once and only its hash is ever persisted."""

    key_id: uuid.UUID
    full_key: str
    secret_hash: str


def issue_secret() -> IssuedSecret:
    key_id = uuid.uuid4()
    secret = secrets.token_hex(32)  # 256 bits, hex so the '_' delimiter stays unambiguous
    full_key = f"{KEY_PREFIX}_{key_id.hex}_{secret}"
    return IssuedSecret(key_id=key_id, full_key=full_key, secret_hash=hash_secret(secret))


def parse_full_key(full_key: str) -> tuple[uuid.UUID, str]:
    """Split a presented key into (key_id, secret) without verifying it."""
    parts = full_key.split("_")
    if len(parts) != 3 or parts[0] != KEY_PREFIX or not parts[2]:
        raise MalformedApiKeyError("credential is not a valid platform API key")
    try:
        key_id = uuid.UUID(hex=parts[1])
    except ValueError as exc:
        raise MalformedApiKeyError("credential is not a valid platform API key") from exc
    return key_id, parts[2]


def hash_secret(secret: str) -> str:
    return hashlib.sha256(secret.encode("ascii")).hexdigest()


def verify_secret(presented_secret: str, stored_hash: str) -> bool:
    return hmac.compare_digest(hash_secret(presented_secret), stored_hash)
