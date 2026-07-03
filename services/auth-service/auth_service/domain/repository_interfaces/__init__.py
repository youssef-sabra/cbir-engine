"""Persistence operations the domain needs, with no knowledge of how.

Implemented by interface_adapters/gateways against whatever infrastructure/
provides (SQLAlchemy + PostgreSQL today).
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod

from cbir_domain_kernel import TenantId

from auth_service.domain.entities import ApiKey, Tenant


class TenantRepository(ABC):
    @abstractmethod
    def add(self, tenant: Tenant) -> None: ...

    @abstractmethod
    def get(self, tenant_id: TenantId) -> Tenant | None: ...

    @abstractmethod
    def get_by_name(self, name: str) -> Tenant | None: ...

    @abstractmethod
    def list(self, limit: int, offset: int) -> list[Tenant]: ...


class ApiKeyRepository(ABC):
    @abstractmethod
    def add(self, api_key: ApiKey) -> None: ...

    @abstractmethod
    def get(self, key_id: uuid.UUID) -> ApiKey | None: ...

    @abstractmethod
    def update(self, api_key: ApiKey) -> None: ...

    @abstractmethod
    def list_for_tenant(self, tenant_id: TenantId) -> list[ApiKey]: ...
