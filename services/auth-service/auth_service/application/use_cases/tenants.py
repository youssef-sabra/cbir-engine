"""Tenant lifecycle use cases (manual provisioning path, pre-self-serve)."""

from __future__ import annotations

from cbir_domain_kernel import InvalidTenantIdError, TenantId

from auth_service.application.dto import CreateTenantInput, TenantOutput
from auth_service.application.errors import TenantNameConflictError, TenantNotFoundError
from auth_service.application.ports import Clock
from auth_service.domain.entities import Tenant
from auth_service.domain.repository_interfaces import TenantRepository
from auth_service.domain.value_objects import PlanTier, TenantStatus


def _present(tenant: Tenant) -> TenantOutput:
    return TenantOutput(
        id=str(tenant.id),
        name=tenant.name,
        plan_tier=tenant.plan_tier.value,
        status=tenant.status.value,
        settings=tenant.settings,
        created_at=tenant.created_at,
        updated_at=tenant.updated_at,
    )


class CreateTenant:
    def __init__(self, tenants: TenantRepository, clock: Clock) -> None:
        self._tenants = tenants
        self._clock = clock

    def execute(self, data: CreateTenantInput) -> TenantOutput:
        name = data.name.strip()
        if not name:
            raise ValueError("tenant name must not be empty")
        if self._tenants.get_by_name(name) is not None:
            raise TenantNameConflictError(f"a tenant named '{name}' already exists")
        now = self._clock.now()
        tenant = Tenant(
            id=TenantId.new(),
            name=name,
            plan_tier=PlanTier(data.plan_tier),
            status=TenantStatus.ACTIVE,
            settings=dict(data.settings),
            created_at=now,
            updated_at=now,
        )
        self._tenants.add(tenant)
        return _present(tenant)


class GetTenant:
    def __init__(self, tenants: TenantRepository) -> None:
        self._tenants = tenants

    def execute(self, tenant_id: str) -> TenantOutput:
        try:
            parsed = TenantId.parse(tenant_id)
        except InvalidTenantIdError as exc:
            raise TenantNotFoundError(f"no tenant with id '{tenant_id}'") from exc
        tenant = self._tenants.get(parsed)
        if tenant is None:
            raise TenantNotFoundError(f"no tenant with id '{tenant_id}'")
        return _present(tenant)


class ListTenants:
    def __init__(self, tenants: TenantRepository) -> None:
        self._tenants = tenants

    def execute(self, limit: int = 50, offset: int = 0) -> list[TenantOutput]:
        return [_present(t) for t in self._tenants.list(limit=limit, offset=offset)]
