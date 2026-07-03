from __future__ import annotations

from cbir_domain_kernel import TenantId

from catalog_service.domain.entities import CatalogItem
from catalog_service.domain.value_objects import ItemStatus
from catalog_service.infrastructure.persistence import CatalogItemRow


def item_to_row(item: CatalogItem) -> CatalogItemRow:
    return CatalogItemRow(
        id=item.id,
        tenant_id=item.tenant_id.value,
        object_key=item.object_key,
        content_type=item.content_type,
        status=item.status.value,
        metadata_=item.metadata,
        external_id=item.external_id,
        size_bytes=item.size_bytes,
        phash=item.phash,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def row_to_item(row: CatalogItemRow) -> CatalogItem:
    return CatalogItem(
        id=row.id,
        tenant_id=TenantId(row.tenant_id),
        object_key=row.object_key,
        content_type=row.content_type,
        status=ItemStatus(row.status),
        metadata=dict(row.metadata_ or {}),
        external_id=row.external_id,
        size_bytes=row.size_bytes,
        phash=row.phash,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )
