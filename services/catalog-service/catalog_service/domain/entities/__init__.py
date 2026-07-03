from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime

from cbir_domain_kernel import TenantId

from catalog_service.domain.value_objects import ItemStatus


@dataclass
class CatalogItem:
    """A single indexable image in a tenant's catalog.

    `object_key` locates the raw bytes in object storage; `metadata` is the
    tenant's arbitrary structured payload (FR1.6) used later for hybrid
    search filtering. `phash` holds the perceptual hash the ingestion worker
    computes for near-duplicate detection (FR1.2).
    """

    id: uuid.UUID
    tenant_id: TenantId
    object_key: str
    content_type: str
    status: ItemStatus
    metadata: dict = field(default_factory=dict)
    external_id: str | None = None
    size_bytes: int | None = None
    phash: str | None = None
    duplicate_of_id: uuid.UUID | None = None
    failure_reason: str | None = None
    indexed_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def mark_uploaded_and_queued(self, size_bytes: int, now: datetime) -> None:
        """Confirmed present in storage and handed to the ingestion pipeline.
        There is no lingering 'uploaded but not queued' state: confirmation
        and enqueue happen atomically from the caller's perspective."""
        self.status = ItemStatus.QUEUED
        self.size_bytes = size_bytes
        self.failure_reason = None
        self.updated_at = now

    def is_downloadable(self) -> bool:
        # Downloadable once the bytes are confirmed present, through every
        # post-confirmation state.
        return self.status in {
            ItemStatus.QUEUED,
            ItemStatus.PROCESSING,
            ItemStatus.INDEXED,
            ItemStatus.DUPLICATE,
            ItemStatus.FAILED,
        }
