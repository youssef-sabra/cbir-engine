"""Relevance-feedback submission (FR3.1, Milestone 9 fast-follow).

A tenant marks a search result relevant/not for a given query, feeding the
future fine-tuning pipeline. Tenant-scoped: feedback can only be attached to
an item the tenant owns, so this can never write feedback against another
tenant's catalog.
"""

from __future__ import annotations

import uuid

from cbir_domain_kernel import TenantId

from catalog_service.application.errors import ItemNotFoundError
from catalog_service.domain.repository_interfaces import (
    CatalogItemRepository,
    FeedbackRepository,
)


class SubmitFeedback:
    def __init__(self, items: CatalogItemRepository, feedback: FeedbackRepository) -> None:
        self._items = items
        self._feedback = feedback

    def execute(self, tenant_id: str, item_id: str, query_ref: str, relevant: bool) -> str:
        try:
            parsed_item = uuid.UUID(item_id)
        except ValueError as exc:
            raise ItemNotFoundError(f"no catalog item with id '{item_id}'") from exc
        if self._items.get(TenantId.parse(tenant_id), parsed_item) is None:
            raise ItemNotFoundError(f"no catalog item with id '{item_id}'")
        feedback_id = uuid.uuid4()
        self._feedback.add(feedback_id, parsed_item, query_ref, relevant)
        return str(feedback_id)
