"""The ingestion pipeline core: process one job.

download bytes -> embed (+ perceptual hash) -> dedup -> index or mark
duplicate. Dependency-injected and infrastructure-free, so the whole
dedup/index decision is unit-tested with fakes. Transient failures raise
TransientError (the worker loop retries); permanent failures raise
PermanentError (dead-lettered immediately).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from cbir_common.vectordb import VectorRecord, VectorStore, collection_name

from ingestion_worker.dedup import find_duplicate
from ingestion_worker.ports import (
    EmbedderClient,
    IndexVersionBumper,
    ItemStore,
    ObjectDownloader,
    PermanentError,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ProcessResult:
    item_id: str
    outcome: str  # "indexed" | "duplicate" | "skipped"
    duplicate_of: str | None = None


class IngestionProcessor:
    def __init__(
        self,
        items: ItemStore,
        downloader: ObjectDownloader,
        embedder: EmbedderClient,
        vector_store: VectorStore,
        index_versions: IndexVersionBumper,
        dedup_hamming_threshold: int,
    ) -> None:
        self._items = items
        self._downloader = downloader
        self._embedder = embedder
        self._vectors = vector_store
        self._index_versions = index_versions
        self._threshold = dedup_hamming_threshold

    def fail(self, item_id: str, reason: str) -> None:
        """Mark an item FAILED with a reason (called by the runner when a job
        is dead-lettered)."""
        self._items.mark_failed(item_id, reason)

    def process(self, item_id: str) -> ProcessResult:
        item = self._items.get(item_id)
        if item is None:
            # Item deleted between enqueue and processing — nothing to do.
            logger.info("ingestion job for unknown item %s; skipping", item_id)
            return ProcessResult(item_id=item_id, outcome="skipped")
        if item.status == "indexed":
            # Idempotent: a redelivered job for an already-indexed item is a
            # no-op, not a re-index (at-least-once queue delivery).
            return ProcessResult(item_id=item_id, outcome="skipped")

        self._items.mark_processing(item_id)

        image_bytes = self._downloader.download(item.object_key)
        vector, phash, model_version = self._embedder.embed_image(image_bytes)
        if not vector:
            raise PermanentError("embedding provider returned an empty vector")

        # Dedup BEFORE the vector-store write, so a near-duplicate never
        # consumes an index slot (FR1.2: avoid redundant indexing).
        existing = self._items.list_indexed_phashes(item.tenant_id)
        duplicate_of = find_duplicate(phash, existing, self._threshold)
        if duplicate_of is not None:
            self._items.mark_duplicate(item_id, phash, duplicate_of)
            return ProcessResult(item_id=item_id, outcome="duplicate", duplicate_of=duplicate_of)

        # Index: upsert the vector with a searchable metadata payload, then
        # record the embedding reference and flip the item to INDEXED.
        self._vectors.ensure_collection(item.tenant_id, dim=len(vector))
        payload = _search_payload(item)
        self._vectors.upsert(
            item.tenant_id, [VectorRecord(id=item_id, vector=vector, payload=payload)]
        )
        self._items.mark_indexed(
            item_id,
            phash=phash,
            collection=collection_name(item.tenant_id),
            vector_id=item_id,
            model_version=model_version,
        )
        # Invalidate the tenant's query caches (Milestone 8). Best-effort.
        try:
            self._index_versions.bump(item.tenant_id)
        except Exception:
            logger.warning("failed to bump index version for tenant %s", item.tenant_id)
        return ProcessResult(item_id=item_id, outcome="indexed")


def _search_payload(item) -> dict:
    """What gets stored alongside the vector for hybrid (vector + filter)
    search. Tenant metadata is flattened in so query-service can filter on it;
    a couple of always-present fields aid enrichment/debugging."""
    payload = {"item_id": item.id}
    if item.external_id:
        payload["external_id"] = item.external_id
    if isinstance(item.metadata, dict):
        for key, value in item.metadata.items():
            # only scalar filterable values in the payload
            if isinstance(value, str | int | float | bool):
                payload[key] = value
    return payload
