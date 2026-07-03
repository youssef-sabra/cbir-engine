"""Environment configuration — the only place environment variables are read.

Values are read once here and passed inward as plain values; no other layer
touches the environment (docs/CLEAN_ARCHITECTURE.md Section 3).
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    service_name: str = "auth-service"
    service_version: str = "0.1.0"

    database_url: str = "postgresql+psycopg://cbir:cbir_local_dev_password@localhost:5432/cbir"
    redis_url: str = "redis://localhost:6379/0"

    # Local-development defaults only. Compose/.env overrides these; a real
    # deployment must set them from a secret manager.
    auth_jwt_secret: str = "local-dev-jwt-secret-not-for-production"
    auth_admin_token: str = "local-dev-admin-token"

    auth_access_token_ttl_seconds: int = 900  # 15 min bounds local-JWT revocation lag
    auth_api_key_grace_seconds: int = 86400  # rotated keys stay valid this long
