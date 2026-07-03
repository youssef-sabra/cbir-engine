"""Persistence operations the catalog domain needs.

Every read/write is tenant-scoped BY SIGNATURE: there is no way to express
"fetch item by id across tenants" through this interface, which makes tenant
isolation (FR4.1) a structural property of the code rather than a per-query
discipline.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod

from cbir_domain_kernel import TenantId

from catalog_service.domain.entities import CatalogItem


class CatalogItemRepository(ABC):
    @abstractmethod
    def add(self, item: CatalogItem) -> None: ...

    @abstractmethod
    def get(self, tenant_id: TenantId, item_id: uuid.UUID) -> CatalogItem | None: ...

    @abstractmethod
    def get_by_external_id(self, tenant_id: TenantId, external_id: str) -> CatalogItem | None: ...

    @abstractmethod
    def list_for_tenant(
        self, tenant_id: TenantId, limit: int, offset: int
    ) -> list[CatalogItem]: ...

    @abstractmethod
    def update(self, item: CatalogItem) -> None: ...

    @abstractmethod
    def delete(self, tenant_id: TenantId, item_id: uuid.UUID) -> bool:
        """Delete the item row and (via database cascade) all derived rows —
        embedding references and feedback. Returns False if no such item."""
