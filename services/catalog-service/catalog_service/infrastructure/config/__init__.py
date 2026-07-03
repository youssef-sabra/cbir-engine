"""Environment configuration — the only place environment variables are read."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    service_name: str = "catalog-service"
    service_version: str = "0.1.0"

    database_url: str = "postgresql+psycopg://cbir:cbir_local_dev_password@localhost:5432/cbir"

    # Redis backs the ingestion queue the worker consumes (Milestone 4).
    redis_url: str = "redis://localhost:6379/0"

    # Gateway-role validation endpoint (see cbir_common.auth).
    auth_service_url: str = "http://localhost:8001"

    # Cap on items registrable in one batch call (protects the API).
    max_batch_items: int = 1000

    # Object storage via the S3 API contract. s3_endpoint_url is where THIS
    # SERVICE talks to storage; s3_presign_endpoint_url is the host embedded
    # in signed URLs handed to CLIENTS. They differ locally because clients
    # live on the host machine ("localhost:9000") while the service reaches
    # MinIO over the Compose network ("minio:9000"). In production both are
    # the same public storage endpoint.
    s3_endpoint_url: str = "http://localhost:9000"
    s3_presign_endpoint_url: str = ""  # empty -> same as s3_endpoint_url
    s3_access_key: str = "cbir_minio_admin"
    s3_secret_key: str = "cbir_local_dev_password"
    s3_bucket_name: str = "cbir-catalog-images"
    s3_region: str = "us-east-1"

    upload_url_ttl_seconds: int = 900
    download_url_ttl_seconds: int = 900

    allowed_content_types: tuple[str, ...] = (
        "image/jpeg",
        "image/png",
        "image/webp",
    )

    @property
    def presign_endpoint(self) -> str:
        return self.s3_presign_endpoint_url or self.s3_endpoint_url
