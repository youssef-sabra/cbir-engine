"""Translate use-case output DTOs into HTTP response schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from catalog_service.application.dto import (
    BatchRegisteredOutput,
    ItemOutput,
    ItemWithDownloadOutput,
    RegisteredItemOutput,
)


class ItemResponse(BaseModel):
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


class PresignedUploadResponse(BaseModel):
    url: str
    method: str
    headers: dict
    expires_in_seconds: int


class RegisteredItemResponse(BaseModel):
    item: ItemResponse
    upload: PresignedUploadResponse


class BatchRegisteredResponse(BaseModel):
    items: list[RegisteredItemResponse]


class ItemWithDownloadResponse(BaseModel):
    item: ItemResponse
    download_url: str | None


def present_item(dto: ItemOutput) -> ItemResponse:
    return ItemResponse(**dto.__dict__)


def present_registered(dto: RegisteredItemOutput) -> RegisteredItemResponse:
    return RegisteredItemResponse(
        item=present_item(dto.item),
        upload=PresignedUploadResponse(
            url=dto.upload.url,
            method=dto.upload.method,
            headers=dto.upload.headers,
            expires_in_seconds=dto.upload.expires_in_seconds,
        ),
    )


def present_batch(dto: BatchRegisteredOutput) -> BatchRegisteredResponse:
    return BatchRegisteredResponse(items=[present_registered(i) for i in dto.items])


def present_item_with_download(dto: ItemWithDownloadOutput) -> ItemWithDownloadResponse:
    return ItemWithDownloadResponse(item=present_item(dto.item), download_url=dto.download_url)
