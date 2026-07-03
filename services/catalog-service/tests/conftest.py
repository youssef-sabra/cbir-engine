"""Test doubles for catalog-service unit tests (no PostgreSQL, MinIO, or
auth-service required). The auth dependency is stubbed with a switchable
tenant so tests can act as tenant A, then tenant B, and prove isolation."""

from __future__ import annotations

import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

import pytest
from cbir_common.auth import TenantContext
from cbir_domain_kernel import TenantId
from fastapi.testclient import TestClient

from catalog_service.application.ports import (
    Clock,
    ObjectStat,
    ObjectStoragePort,
    PresignedUpload,
)
from catalog_service.application.use_cases.bundle import UseCaseBundle
from catalog_service.application.use_cases.items import (
    ConfirmCatalogItemUpload,
    DeleteCatalogItem,
    GetCatalogItem,
    ListCatalogItems,
    RegisterCatalogItem,
)
from catalog_service.domain.entities import CatalogItem
from catalog_service.domain.repository_interfaces import CatalogItemRepository
from catalog_service.entrypoint.composition_root import build_app
from catalog_service.infrastructure.config import Settings

ALLOWED_TYPES = ("image/jpeg", "image/png", "image/webp")


class InMemoryCatalogItemRepository(CatalogItemRepository):
    def __init__(self) -> None:
        self.rows: dict[uuid.UUID, CatalogItem] = {}

    def add(self, item: CatalogItem) -> None:
        self.rows[item.id] = item

    def get(self, tenant_id: TenantId, item_id: uuid.UUID) -> CatalogItem | None:
        item = self.rows.get(item_id)
        if item is None or str(item.tenant_id) != str(tenant_id):
            return None
        return item

    def get_by_external_id(self, tenant_id: TenantId, external_id: str) -> CatalogItem | None:
        return next(
            (
                i
                for i in self.rows.values()
                if str(i.tenant_id) == str(tenant_id) and i.external_id == external_id
            ),
            None,
        )

    def list_for_tenant(self, tenant_id: TenantId, limit: int, offset: int) -> list[CatalogItem]:
        mine = [i for i in self.rows.values() if str(i.tenant_id) == str(tenant_id)]
        return mine[offset : offset + limit]

    def update(self, item: CatalogItem) -> None:
        self.rows[item.id] = item

    def delete(self, tenant_id: TenantId, item_id: uuid.UUID) -> bool:
        if self.get(tenant_id, item_id) is None:
            return False
        del self.rows[item_id]
        return True


class FakeObjectStorage(ObjectStoragePort):
    """Objects 'exist' once a test calls put(); URLs are recognizable fakes."""

    def __init__(self) -> None:
        self.objects: dict[str, int] = {}
        self.deleted: list[str] = []

    def put(self, object_key: str, size_bytes: int = 42) -> None:
        self.objects[object_key] = size_bytes

    def ensure_bucket(self) -> None:
        pass

    def presign_upload(
        self, object_key: str, content_type: str, expires_in_seconds: int
    ) -> PresignedUpload:
        return PresignedUpload(
            url=f"https://fake-storage/upload/{object_key}",
            method="PUT",
            headers={"Content-Type": content_type},
            expires_in_seconds=expires_in_seconds,
        )

    def presign_download(self, object_key: str, expires_in_seconds: int) -> str:
        return f"https://fake-storage/download/{object_key}"

    def stat_object(self, object_key: str) -> ObjectStat | None:
        if object_key not in self.objects:
            return None
        return ObjectStat(size_bytes=self.objects[object_key])

    def delete_object(self, object_key: str) -> None:
        self.deleted.append(object_key)
        self.objects.pop(object_key, None)


class MutableClock(Clock):
    def __init__(self) -> None:
        self.current = datetime(2026, 7, 3, 12, 0, 0, tzinfo=timezone.utc)

    def now(self) -> datetime:
        return self.current

    def advance(self, **kwargs) -> None:
        self.current += timedelta(**kwargs)


class SwitchableAuth:
    """Stub for the gateway-role auth dependency: whatever tenant this is set
    to is who the request 'is'. Lets tests act as tenant A then tenant B."""

    def __init__(self) -> None:
        self.tenant_id = str(uuid.uuid4())
        self.scopes = ["catalog:read", "catalog:write"]

    def __call__(self) -> TenantContext:
        return TenantContext(
            tenant_id=self.tenant_id,
            api_key_id=str(uuid.uuid4()),
            scopes=self.scopes,
            plan_tier="free",
        )


class World:
    def __init__(self) -> None:
        self.items = InMemoryCatalogItemRepository()
        self.storage = FakeObjectStorage()
        self.clock = MutableClock()
        self.auth = SwitchableAuth()

    def bundle(self) -> UseCaseBundle:
        return UseCaseBundle(
            register_item=RegisterCatalogItem(
                self.items,
                self.storage,
                self.clock,
                allowed_content_types=ALLOWED_TYPES,
                upload_url_ttl_seconds=900,
            ),
            confirm_upload=ConfirmCatalogItemUpload(self.items, self.storage, self.clock),
            get_item=GetCatalogItem(self.items, self.storage, download_url_ttl_seconds=900),
            list_items=ListCatalogItems(self.items),
            delete_item=DeleteCatalogItem(self.items, self.storage),
        )


@pytest.fixture
def world() -> World:
    return World()


@pytest.fixture
def client(world: World) -> TestClient:
    @contextmanager
    def unit_of_work():
        yield world.bundle()

    settings = Settings(
        database_url="postgresql+psycopg://nobody:nothing@127.0.0.1:9/none",
        auth_service_url="http://127.0.0.1:9",
    )
    app = build_app(
        settings=settings,
        unit_of_work_factory=unit_of_work,
        require_read=world.auth,
        require_write=world.auth,
    )
    return TestClient(app)


def register_item(client: TestClient, **overrides) -> dict:
    payload = {"content_type": "image/jpeg", "metadata": {"category": "shoes"}}
    payload.update(overrides)
    response = client.post("/v1/items", json=payload)
    assert response.status_code == 201, response.text
    return response.json()
