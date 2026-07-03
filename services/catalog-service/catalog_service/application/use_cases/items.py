"""Catalog item use cases: the Milestone 3 storage-foundation slice.

Register (metadata row + signed upload URL) -> Confirm (bytes verified in
object storage) -> Get/List (with signed download URLs) -> Delete (the
right-to-erasure workflow: object AND all derived metadata rows).

Milestone 4 builds the asynchronous ingestion pipeline (dedup, embedding
queue) on top of exactly these seams.
"""

from __future__ import annotations

import uuid

from cbir_domain_kernel import TenantId

from catalog_service.application.dto import (
    ItemOutput,
    ItemWithDownloadOutput,
    RegisteredItemOutput,
    RegisterItemInput,
)
from catalog_service.application.errors import (
    DuplicateExternalIdError,
    ItemNotFoundError,
    UnsupportedContentTypeError,
    UploadNotConfirmableError,
)
from catalog_service.application.ports import Clock, ObjectStoragePort
from catalog_service.domain.entities import CatalogItem
from catalog_service.domain.repository_interfaces import CatalogItemRepository
from catalog_service.domain.value_objects import ItemStatus


def _present(item: CatalogItem) -> ItemOutput:
    return ItemOutput(
        id=str(item.id),
        tenant_id=str(item.tenant_id),
        status=item.status.value,
        content_type=item.content_type,
        metadata=item.metadata,
        external_id=item.external_id,
        size_bytes=item.size_bytes,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def object_key_for(tenant_id: TenantId, item_id: uuid.UUID) -> str:
    """Tenant-prefixed keys make per-tenant lifecycle policies and bulk
    erasure tractable at the storage layer as well."""
    return f"tenants/{tenant_id}/items/{item_id}"


class RegisterCatalogItem:
    def __init__(
        self,
        items: CatalogItemRepository,
        storage: ObjectStoragePort,
        clock: Clock,
        allowed_content_types: tuple[str, ...],
        upload_url_ttl_seconds: int,
    ) -> None:
        self._items = items
        self._storage = storage
        self._clock = clock
        self._allowed_content_types = allowed_content_types
        self._upload_url_ttl_seconds = upload_url_ttl_seconds

    def execute(self, data: RegisterItemInput) -> RegisteredItemOutput:
        if data.content_type not in self._allowed_content_types:
            raise UnsupportedContentTypeError(
                f"content type '{data.content_type}' not supported; "
                f"allowed: {sorted(self._allowed_content_types)}"
            )
        tenant_id = TenantId.parse(data.tenant_id)
        if data.external_id is not None and (
            self._items.get_by_external_id(tenant_id, data.external_id) is not None
        ):
            raise DuplicateExternalIdError(
                f"an item with external_id '{data.external_id}' already exists for this tenant"
            )
        now = self._clock.now()
        item_id = uuid.uuid4()
        item = CatalogItem(
            id=item_id,
            tenant_id=tenant_id,
            object_key=object_key_for(tenant_id, item_id),
            content_type=data.content_type,
            status=ItemStatus.PENDING_UPLOAD,
            metadata=dict(data.metadata),
            external_id=data.external_id,
            created_at=now,
            updated_at=now,
        )
        self._items.add(item)
        upload = self._storage.presign_upload(
            item.object_key, item.content_type, self._upload_url_ttl_seconds
        )
        return RegisteredItemOutput(item=_present(item), upload=upload)


class ConfirmCatalogItemUpload:
    def __init__(
        self, items: CatalogItemRepository, storage: ObjectStoragePort, clock: Clock
    ) -> None:
        self._items = items
        self._storage = storage
        self._clock = clock

    def execute(self, tenant_id: str, item_id: str) -> ItemOutput:
        item = _get_item_or_raise(self._items, tenant_id, item_id)
        stat = self._storage.stat_object(item.object_key)
        if stat is None:
            raise UploadNotConfirmableError(
                "no object found in storage for this item — upload via the signed URL first"
            )
        item.mark_uploaded(size_bytes=stat.size_bytes, now=self._clock.now())
        self._items.update(item)
        return _present(item)


class GetCatalogItem:
    def __init__(
        self,
        items: CatalogItemRepository,
        storage: ObjectStoragePort,
        download_url_ttl_seconds: int,
    ) -> None:
        self._items = items
        self._storage = storage
        self._download_url_ttl_seconds = download_url_ttl_seconds

    def execute(self, tenant_id: str, item_id: str) -> ItemWithDownloadOutput:
        item = _get_item_or_raise(self._items, tenant_id, item_id)
        download_url = None
        if item.is_downloadable():
            download_url = self._storage.presign_download(
                item.object_key, self._download_url_ttl_seconds
            )
        return ItemWithDownloadOutput(item=_present(item), download_url=download_url)


class ListCatalogItems:
    def __init__(self, items: CatalogItemRepository) -> None:
        self._items = items

    def execute(self, tenant_id: str, limit: int = 50, offset: int = 0) -> list[ItemOutput]:
        parsed = TenantId.parse(tenant_id)
        return [_present(i) for i in self._items.list_for_tenant(parsed, limit, offset)]


class DeleteCatalogItem:
    """Right-to-erasure workflow (NFR13): removes the stored object first,
    then the metadata row — and with it, via database cascade, every derived
    row (embedding references, feedback). Object deletion is idempotent, so
    a failure after the object is gone but before the rows are deleted is
    safely retryable."""

    def __init__(self, items: CatalogItemRepository, storage: ObjectStoragePort) -> None:
        self._items = items
        self._storage = storage

    def execute(self, tenant_id: str, item_id: str) -> None:
        item = _get_item_or_raise(self._items, tenant_id, item_id)
        self._storage.delete_object(item.object_key)
        self._items.delete(TenantId.parse(tenant_id), item.id)


def _get_item_or_raise(
    items: CatalogItemRepository, tenant_id: str, item_id: str
) -> CatalogItem:
    not_found = ItemNotFoundError(f"no catalog item with id '{item_id}'")
    try:
        parsed_item_id = uuid.UUID(item_id)
    except ValueError:
        raise not_found from None
    item = items.get(TenantId.parse(tenant_id), parsed_item_id)
    if item is None:
        # Same 404 whether the item doesn't exist or belongs to another
        # tenant — existence itself is tenant-scoped information.
        raise not_found
    return item
