"""Environment configuration — the only place env vars are read."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    service_name: str = "query-service"
    service_version: str = "0.1.0"

    auth_service_url: str = "http://localhost:8001"
    ai_service_url: str = "http://localhost:8003"
    qdrant_url: str = "http://localhost:6333"
    redis_url: str = "redis://localhost:6379/0"

    # Result/embedding caching (Milestone 8). Set enable_cache=false to run the
    # uncached path (also the automatic fallback if Redis is unreachable).
    enable_cache: bool = True
