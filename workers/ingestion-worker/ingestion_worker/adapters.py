"""Concrete adapters: the outer, technology-specific layer.

The worker owns thin SQLAlchemy models for the two tables it touches
(catalog_items, embedding_refs). catalog-service's Alembic migrations remain
the single source of truth for that schema; these models mirror the columns
the worker reads/writes and are never migrated from here.
"""

from __future__ import annotations

import base64
import uuid
from datetime import datetime, timezone

import boto3
import httpx
import redis
from botocore.client import Config
from botocore.exceptions import BotoCoreError, ClientError
from sqlalchemy import select
from sqlalchemy.orm import Session

from ingestion_worker.models import CatalogItemRow, EmbeddingRefRow
from ingestion_worker.ports import (
    EmbedderClient,
    IndexVersionBumper,
    ItemStore,
    ItemView,
    ObjectDownloader,
    PermanentError,
    TransientError,
)

INDEX_VERSION_KEY = "cbir:index-version:{tenant_id}"


def _now() -> datetime:
    return datetime.now(timezone.utc)


class SqlAlchemyItemStore(ItemStore):
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, item_id: str) -> ItemView | None:
        row = self._session.get(CatalogItemRow, uuid.UUID(item_id))
        if row is None:
            return None
        return ItemView(
            id=str(row.id),
            tenant_id=str(row.tenant_id),
            object_key=row.object_key,
            content_type=row.content_type,
            metadata=dict(row.metadata_ or {}),
            external_id=row.external_id,
            status=row.status,
        )

    def mark_processing(self, item_id: str) -> None:
        self._update(item_id, status="processing")

    def mark_indexed(
        self, item_id: str, phash: str, collection: str, vector_id: str, model_version: str
    ) -> None:
        now = _now()
        self._update(item_id, status="indexed", phash=phash, indexed_at=now, failure_reason=None)
        self._session.add(
            EmbeddingRefRow(
                id=uuid.uuid4(),
                item_id=uuid.UUID(item_id),
                vector_db_collection=collection,
                vector_id=vector_id,
                model_version=model_version,
                created_at=now,
            )
        )

    def mark_duplicate(self, item_id: str, phash: str, duplicate_of_id: str) -> None:
        self._update(
            item_id,
            status="duplicate",
            phash=phash,
            duplicate_of_id=uuid.UUID(duplicate_of_id),
        )

    def mark_failed(self, item_id: str, reason: str) -> None:
        self._update(item_id, status="failed", failure_reason=reason[:1000])

    def list_indexed_phashes(self, tenant_id: str) -> list[tuple[str, str]]:
        rows = self._session.execute(
            select(CatalogItemRow.id, CatalogItemRow.phash)
            .where(
                CatalogItemRow.tenant_id == uuid.UUID(tenant_id),
                CatalogItemRow.status == "indexed",
                CatalogItemRow.phash.is_not(None),
            )
            .order_by(CatalogItemRow.indexed_at.desc())
        )
        return [(str(r[0]), r[1]) for r in rows]

    def _update(self, item_id: str, **fields) -> None:
        row = self._session.get(CatalogItemRow, uuid.UUID(item_id))
        if row is None:
            return
        for key, value in fields.items():
            setattr(row, key, value)
        row.updated_at = _now()


class S3ObjectDownloader(ObjectDownloader):
    def __init__(
        self, endpoint_url: str, access_key: str, secret_key: str, bucket: str, region: str
    ) -> None:
        self._bucket = bucket
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
            config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
        )

    def download(self, object_key: str) -> bytes:
        try:
            response = self._client.get_object(Bucket=self._bucket, Key=object_key)
            return response["Body"].read()
        except ClientError as exc:
            code = str(exc.response.get("Error", {}).get("Code", ""))
            if code in ("NoSuchKey", "404", "NoSuchBucket"):
                raise PermanentError(f"object '{object_key}' not found in storage") from exc
            raise TransientError("object storage error") from exc
        except BotoCoreError as exc:
            raise TransientError("object storage unreachable") from exc


class AiServiceEmbedderClient(EmbedderClient):
    def __init__(self, base_url: str, timeout_seconds: float = 30.0) -> None:
        self._client = httpx.Client(base_url=base_url, timeout=timeout_seconds)

    def embed_image(self, image_bytes: bytes) -> tuple[list[float], str, str]:
        payload = {
            "inputs": [
                {"modality": "image", "image_base64": base64.b64encode(image_bytes).decode()}
            ],
            "include_phash": True,
        }
        try:
            response = self._client.post("/internal/embed", json=payload)
        except httpx.HTTPError as exc:
            raise TransientError("ai-service unreachable") from exc
        if response.status_code == 422:
            raise PermanentError(f"ai-service rejected the image: {response.text}")
        if response.status_code != 200:
            raise TransientError(f"ai-service returned {response.status_code}")
        data = response.json()
        result = data["results"][0]
        return result["vector"], result["phash"], data["model_version"]


class RedisIndexVersionBumper(IndexVersionBumper):
    def __init__(self, client: redis.Redis) -> None:
        self._redis = client

    def bump(self, tenant_id: str) -> None:
        self._redis.incr(INDEX_VERSION_KEY.format(tenant_id=tenant_id))
