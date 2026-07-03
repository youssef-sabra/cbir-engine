from __future__ import annotations

import uuid
from datetime import datetime, timezone

from cbir_domain_kernel import TenantId
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from catalog_service.domain.entities import CatalogItem
from catalog_service.domain.repository_interfaces import (
    CatalogItemRepository,
    FeedbackRepository,
)
from catalog_service.infrastructure.persistence import CatalogItemRow, FeedbackRow
from catalog_service.interface_adapters import mappers


class SqlAlchemyCatalogItemRepository(CatalogItemRepository):
    """Every query below filters by tenant_id — the repository interface makes
    anything else inexpressible (FR4.1)."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, item: CatalogItem) -> None:
        self._session.add(mappers.item_to_row(item))

    def get(self, tenant_id: TenantId, item_id: uuid.UUID) -> CatalogItem | None:
        row = self._session.scalar(
            select(CatalogItemRow).where(
                CatalogItemRow.id == item_id,
                CatalogItemRow.tenant_id == tenant_id.value,
            )
        )
        return mappers.row_to_item(row) if row else None

    def get_by_external_id(self, tenant_id: TenantId, external_id: str) -> CatalogItem | None:
        row = self._session.scalar(
            select(CatalogItemRow).where(
                CatalogItemRow.tenant_id == tenant_id.value,
                CatalogItemRow.external_id == external_id,
            )
        )
        return mappers.row_to_item(row) if row else None

    def list_for_tenant(
        self, tenant_id: TenantId, limit: int, offset: int, status=None
    ) -> list[CatalogItem]:
        query = select(CatalogItemRow).where(CatalogItemRow.tenant_id == tenant_id.value)
        if status is not None:
            query = query.where(CatalogItemRow.status == status.value)
        rows = self._session.scalars(
            query.order_by(CatalogItemRow.created_at).limit(limit).offset(offset)
        )
        return [mappers.row_to_item(r) for r in rows]

    def update(self, item: CatalogItem) -> None:
        self._session.merge(mappers.item_to_row(item))

    def delete(self, tenant_id: TenantId, item_id: uuid.UUID) -> bool:
        # embedding_refs and feedback rows cascade via their FK constraints
        # (see migration 0001_create_data_layer).
        result = self._session.execute(
            delete(CatalogItemRow).where(
                CatalogItemRow.id == item_id,
                CatalogItemRow.tenant_id == tenant_id.value,
            )
        )
        return result.rowcount > 0


class SqlAlchemyFeedbackRepository(FeedbackRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(
        self, feedback_id: uuid.UUID, item_id: uuid.UUID, query_ref: str, relevant: bool
    ) -> None:
        self._session.add(
            FeedbackRow(
                id=feedback_id,
                item_id=item_id,
                query_ref=query_ref,
                relevant=relevant,
                created_at=datetime.now(timezone.utc),
            )
        )
