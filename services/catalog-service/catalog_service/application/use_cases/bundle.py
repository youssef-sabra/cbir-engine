from __future__ import annotations

from dataclasses import dataclass

from catalog_service.application.use_cases.items import (
    ConfirmCatalogItemUpload,
    DeleteCatalogItem,
    GetCatalogItem,
    ListCatalogItems,
    RegisterCatalogItem,
)


@dataclass(frozen=True)
class UseCaseBundle:
    register_item: RegisterCatalogItem
    confirm_upload: ConfirmCatalogItemUpload
    get_item: GetCatalogItem
    list_items: ListCatalogItems
    delete_item: DeleteCatalogItem
