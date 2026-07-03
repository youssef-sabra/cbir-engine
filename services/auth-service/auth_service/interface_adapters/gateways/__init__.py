"""Concrete repository implementations: the seam where dependency inversion
happens. These implement the domain's repository interfaces on top of the
SQLAlchemy machinery provided by infrastructure/persistence."""

from __future__ import annotations

import uuid

from cbir_domain_kernel import TenantId
from sqlalchemy import select
from sqlalchemy.orm import Session

from auth_service.domain.entities import ApiKey, Tenant
from auth_service.domain.repository_interfaces import ApiKeyRepository, TenantRepository
from auth_service.infrastructure.persistence import ApiKeyRow, TenantRow
from auth_service.interface_adapters import mappers


class SqlAlchemyTenantRepository(TenantRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, tenant: Tenant) -> None:
        self._session.add(mappers.tenant_to_row(tenant))

    def get(self, tenant_id: TenantId) -> Tenant | None:
        row = self._session.get(TenantRow, tenant_id.value)
        return mappers.row_to_tenant(row) if row else None

    def get_by_name(self, name: str) -> Tenant | None:
        row = self._session.scalar(select(TenantRow).where(TenantRow.name == name))
        return mappers.row_to_tenant(row) if row else None

    def list(self, limit: int, offset: int) -> list[Tenant]:
        rows = self._session.scalars(
            select(TenantRow).order_by(TenantRow.created_at).limit(limit).offset(offset)
        )
        return [mappers.row_to_tenant(r) for r in rows]


class SqlAlchemyApiKeyRepository(ApiKeyRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, api_key: ApiKey) -> None:
        self._session.add(mappers.api_key_to_row(api_key))

    def get(self, key_id: uuid.UUID) -> ApiKey | None:
        row = self._session.get(ApiKeyRow, key_id)
        return mappers.row_to_api_key(row) if row else None

    def update(self, api_key: ApiKey) -> None:
        self._session.merge(mappers.api_key_to_row(api_key))

    def list_for_tenant(self, tenant_id: TenantId) -> list[ApiKey]:
        rows = self._session.scalars(
            select(ApiKeyRow)
            .where(ApiKeyRow.tenant_id == tenant_id.value)
            .order_by(ApiKeyRow.created_at)
        )
        return [mappers.row_to_api_key(r) for r in rows]
