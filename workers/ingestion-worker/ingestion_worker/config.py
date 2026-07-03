"""Environment configuration — the only place env vars are read."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    service_name: str = "ingestion-worker"

    database_url: str = "postgresql+psycopg://cbir:cbir_local_dev_password@localhost:5432/cbir"
    redis_url: str = "redis://localhost:6379/0"
    qdrant_url: str = "http://localhost:6333"
    ai_service_url: str = "http://localhost:8003"

    # S3 (object storage) — the worker downloads bytes to embed them.
    s3_endpoint_url: str = "http://localhost:9000"
    s3_access_key: str = "cbir_minio_admin"
    s3_secret_key: str = "cbir_local_dev_password"
    s3_bucket_name: str = "cbir-catalog-images"
    s3_region: str = "us-east-1"

    # Ingestion queue + dead-letter queue keys (must match catalog-service's
    # producer: cbir:ingest:queue).
    queue_key: str = "cbir:ingest:queue"
    dlq_key: str = "cbir:ingest:dlq"

    # Retry policy for transient failures.
    max_attempts: int = 3
    retry_backoff_seconds: float = 2.0

    # pHash near-duplicate threshold (max Hamming distance, in bits, over the
    # 64-bit average hash). 0 = only bit-identical hashes count as duplicates.
    dedup_hamming_threshold: int = 5

    # BRPOP block timeout; also how often an idle worker re-checks for shutdown.
    poll_timeout_seconds: int = 5
