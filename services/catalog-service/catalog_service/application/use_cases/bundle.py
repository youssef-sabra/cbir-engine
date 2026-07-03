from __future__ import annotations

from dataclasses import dataclass

from catalog_service.application.use_cases.feedback import SubmitFeedback
from catalog_service.application.use_cases.items import (
    BatchRegisterCatalogItems,
    ConfirmCatalogItemUpload,
    DeleteCatalogItem,
    GetCatalogItem,
    ListCatalogItems,
    RegisterCatalogItem,
)


@dataclass(frozen=True)
class UseCaseBundle:
    register_item: RegisterCatalogItem
    batch_register: BatchRegisterCatalogItems
    confirm_upload: ConfirmCatalogItemUpload
    get_item: GetCatalogItem
    list_items: ListCatalogItems
    delete_item: DeleteCatalogItem
    submit_feedback: SubmitFeedback
