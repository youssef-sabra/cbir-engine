"""In-memory fakes for worker unit tests. No PostgreSQL, Redis, MinIO, Qdrant,
or ai-service required — the processor and runner are exercised entirely
through their injected ports."""

from __future__ import annotations

from contextlib import contextmanager

import pytest
from cbir_common.vectordb import InMemoryVectorStore

from ingestion_worker.config import Settings
from ingestion_worker.ports import (
    EmbedderClient,
    IndexVersionBumper,
    ItemStore,
    ItemView,
    ObjectDownloader,
    PermanentError,
    TransientError,
)
from ingestion_worker.processor import IngestionProcessor


class FakeItemStore(ItemStore):
    def __init__(self) -> None:
        self.items: dict[str, ItemView] = {}
        self.indexed: dict[str, str] = {}  # item_id -> phash
        self.duplicates: dict[str, str] = {}  # item_id -> duplicate_of
        self.failed: dict[str, str] = {}  # item_id -> reason
        self.embedding_refs: list[tuple[str, str, str]] = []  # (item_id, collection, model)

    def add(self, item: ItemView) -> None:
        self.items[item.id] = item

    def get(self, item_id: str) -> ItemView | None:
        return self.items.get(item_id)

    def mark_processing(self, item_id: str) -> None:
        self.items[item_id].status = "processing"

    def mark_indexed(self, item_id, phash, collection, vector_id, model_version) -> None:
        self.items[item_id].status = "indexed"
        self.indexed[item_id] = phash
        self.embedding_refs.append((item_id, collection, model_version))

    def mark_duplicate(self, item_id, phash, duplicate_of_id) -> None:
        self.items[item_id].status = "duplicate"
        self.duplicates[item_id] = duplicate_of_id

    def mark_failed(self, item_id, reason) -> None:
        if item_id in self.items:
            self.items[item_id].status = "failed"
        self.failed[item_id] = reason

    def list_indexed_phashes(self, tenant_id: str) -> list[tuple[str, str]]:
        return [
            (iid, self.indexed[iid])
            for iid, item in self.items.items()
            if item.tenant_id == tenant_id and item.status == "indexed" and iid in self.indexed
        ]


class FakeDownloader(ObjectDownloader):
    def __init__(self) -> None:
        self.blobs: dict[str, bytes] = {}
        self.raise_transient = False

    def put(self, object_key: str, data: bytes) -> None:
        self.blobs[object_key] = data

    def download(self, object_key: str) -> bytes:
        if self.raise_transient:
            raise TransientError("storage down")
        if object_key not in self.blobs:
            raise PermanentError("missing object")
        return self.blobs[object_key]


class FakeEmbedder(EmbedderClient):
    """Maps image bytes to a deterministic (vector, phash). Tests set the phash
    per blob to control dedup outcomes precisely."""

    def __init__(self) -> None:
        self.by_bytes: dict[bytes, tuple[list[float], str]] = {}
        self.raise_transient = False
        self.raise_permanent = False
        self.model_version = "test-embed-v1"

    def register(self, data: bytes, vector: list[float], phash: str) -> None:
        self.by_bytes[data] = (vector, phash)

    def embed_image(self, image_bytes: bytes) -> tuple[list[float], str, str]:
        if self.raise_transient:
            raise TransientError("ai-service down")
        if self.raise_permanent:
            raise PermanentError("bad image")
        vector, phash = self.by_bytes[image_bytes]
        return vector, phash, self.model_version


class FakeIndexBumper(IndexVersionBumper):
    def __init__(self) -> None:
        self.bumped: list[str] = []

    def bump(self, tenant_id: str) -> None:
        self.bumped.append(tenant_id)


class WorkerWorld:
    def __init__(self, threshold: int = 5) -> None:
        self.items = FakeItemStore()
        self.downloader = FakeDownloader()
        self.embedder = FakeEmbedder()
        self.vectors = InMemoryVectorStore()
        self.bumper = FakeIndexBumper()
        self.threshold = threshold

    def processor(self) -> IngestionProcessor:
        return IngestionProcessor(
            items=self.items,
            downloader=self.downloader,
            embedder=self.embedder,
            vector_store=self.vectors,
            index_versions=self.bumper,
            dedup_hamming_threshold=self.threshold,
        )

    @contextmanager
    def processor_factory(self):
        yield self.processor()

    def seed_item(self, item_id: str, tenant: str, data: bytes, phash: str, vector=None) -> None:
        key = f"tenants/{tenant}/items/{item_id}"
        self.items.add(
            ItemView(
                id=item_id,
                tenant_id=tenant,
                object_key=key,
                content_type="image/jpeg",
                metadata={"category": "shoes"},
                external_id=None,
                status="queued",
            )
        )
        self.downloader.put(key, data)
        self.embedder.register(data, vector or [1.0, 0.0, 0.0], phash)


@pytest.fixture
def world() -> WorkerWorld:
    return WorkerWorld()


@pytest.fixture
def settings() -> Settings:
    return Settings(max_attempts=3, retry_backoff_seconds=0.0)
