from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from catalog_service.application.ports import PresignedUpload


@dataclass(frozen=True)
class RegisterItemInput:
    tenant_id: str
    content_type: str
    metadata: dict = field(default_factory=dict)
    external_id: str | None = None


@dataclass(frozen=True)
class ItemOutput:
    id: str
    tenant_id: str
    status: str
    content_type: str
    metadata: dict
    external_id: str | None
    size_bytes: int | None
    duplicate_of_id: str | None
    failure_reason: str | None
    indexed_at: datetime | None
    created_at: datetime | None
    updated_at: datetime | None


@dataclass(frozen=True)
class RegisteredItemOutput:
    item: ItemOutput
    upload: PresignedUpload


@dataclass(frozen=True)
class BatchRegisterInput:
    tenant_id: str
    items: list[RegisterItemInput]


@dataclass(frozen=True)
class BatchRegisteredOutput:
    items: list[RegisteredItemOutput]


@dataclass(frozen=True)
class ItemWithDownloadOutput:
    item: ItemOutput
    download_url: str | None  # present only once the object is uploaded
