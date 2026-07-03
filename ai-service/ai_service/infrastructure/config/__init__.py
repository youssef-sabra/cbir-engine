"""Environment configuration — the only place environment variables are read."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    service_name: str = "ai-service"
    service_version: str = "0.1.0"

    # Which encoder to load. "local" is the deterministic CPU default that
    # needs no GPU/model download; "siglip2"/"dinov2" select the real
    # adapters (which require torch + weights and raise a clear error until
    # those are provisioned). See infrastructure/embedding.
    embedding_provider: str = "local"

    # Blend weight for the compositional modifier in the default reranker.
    rerank_modifier_weight: float = 0.5
