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
    search filtering. `phash` is reserved for Milestone 4 deduplication.
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
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def mark_uploaded(self, size_bytes: int, now: datetime) -> None:
        self.status = ItemStatus.UPLOADED
        self.size_bytes = size_bytes
        self.updated_at = now

    def is_downloadable(self) -> bool:
        return self.status is ItemStatus.UPLOADED
