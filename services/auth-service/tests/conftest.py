"""Test doubles: in-memory implementations of every port and repository.

Unit tests run with zero external dependencies (no PostgreSQL, no Redis) —
the same rule hello-world-service established in Milestone 1. Real-backend
behavior is covered by tests/e2e against the running Compose stack.
"""

from __future__ import annotations

import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

import pytest
from cbir_domain_kernel import TenantId
from fastapi.testclient import TestClient

from auth_service.application.ports import (
    Clock,
    RateLimitDecision,
    RateLimiterPort,
    RevocationListPort,
)
from auth_service.application.use_cases.api_keys import (
    IssueApiKey,
    ListApiKeys,
    RevokeApiKey,
    RotateApiKey,
)
from auth_service.application.use_cases.bundle import UseCaseBundle
from auth_service.application.use_cases.credentials import (
    ValidateAccessTokenCredential,
    ValidateApiKeyCredential,
)
from auth_service.application.use_cases.tenants import CreateTenant, GetTenant, ListTenants
from auth_service.application.use_cases.tokens import IssueAccessToken
from auth_service.domain.entities import ApiKey, Tenant
from auth_service.domain.repository_interfaces import ApiKeyRepository, TenantRepository
from auth_service.entrypoint.composition_root import build_app
from auth_service.infrastructure.config import Settings
from auth_service.infrastructure.security import JwtTokenSigner, JwtTokenVerifier

TEST_JWT_SECRET = "unit-test-jwt-secret"
TEST_ADMIN_TOKEN = "unit-test-admin-token"


class InMemoryTenantRepository(TenantRepository):
    def __init__(self) -> None:
        self.rows: dict[str, Tenant] = {}

    def add(self, tenant: Tenant) -> None:
        self.rows[str(tenant.id)] = tenant

    def get(self, tenant_id: TenantId) -> Tenant | None:
        return self.rows.get(str(tenant_id))

    def get_by_name(self, name: str) -> Tenant | None:
        return next((t for t in self.rows.values() if t.name == name), None)

    def list(self, limit: int, offset: int) -> list[Tenant]:
        return list(self.rows.values())[offset : offset + limit]


class InMemoryApiKeyRepository(ApiKeyRepository):
    def __init__(self) -> None:
        self.rows: dict[uuid.UUID, ApiKey] = {}

    def add(self, api_key: ApiKey) -> None:
        self.rows[api_key.id] = api_key

    def get(self, key_id: uuid.UUID) -> ApiKey | None:
        return self.rows.get(key_id)

    def update(self, api_key: ApiKey) -> None:
        self.rows[api_key.id] = api_key

    def list_for_tenant(self, tenant_id: TenantId) -> list[ApiKey]:
        return [k for k in self.rows.values() if str(k.tenant_id) == str(tenant_id)]


class CountingRateLimiter(RateLimiterPort):
    """Real fixed-window semantics, in memory, driven by the test clock."""

    def __init__(self, clock: MutableClock) -> None:
        self._clock = clock
        self._counts: dict[tuple[str, int], int] = {}

    def hit(self, bucket: str, limit_per_minute: int) -> RateLimitDecision:
        epoch = int(self._clock.now().timestamp())
        window = epoch - (epoch % 60)
        count = self._counts.get((bucket, window), 0) + 1
        self._counts[(bucket, window)] = count
        if count > limit_per_minute:
            return RateLimitDecision(False, limit_per_minute, 0, window + 60 - epoch)
        return RateLimitDecision(True, limit_per_minute, limit_per_minute - count, 0)


class InMemoryRevocationList(RevocationListPort):
    def __init__(self) -> None:
        self.revoked: set[str] = set()

    def revoke(self, api_key_id: str) -> None:
        self.revoked.add(api_key_id)

    def is_revoked(self, api_key_id: str) -> bool:
        return api_key_id in self.revoked


class MutableClock(Clock):
    def __init__(self) -> None:
        self.current = datetime(2026, 7, 3, 12, 0, 0, tzinfo=timezone.utc)

    def now(self) -> datetime:
        return self.current

    def advance(self, **kwargs) -> None:
        self.current += timedelta(**kwargs)


class World:
    """Everything a test needs to reach behind the API surface."""

    def __init__(self) -> None:
        self.tenants = InMemoryTenantRepository()
        self.keys = InMemoryApiKeyRepository()
        self.clock = MutableClock()
        self.rate_limiter = CountingRateLimiter(self.clock)
        self.revocation_list = InMemoryRevocationList()
        self.signer = JwtTokenSigner(TEST_JWT_SECRET)
        self.verifier = JwtTokenVerifier(TEST_JWT_SECRET)

    def bundle(self) -> UseCaseBundle:
        validate_api_key = ValidateApiKeyCredential(
            self.tenants, self.keys, self.rate_limiter, self.clock
        )
        return UseCaseBundle(
            create_tenant=CreateTenant(self.tenants, self.clock),
            get_tenant=GetTenant(self.tenants),
            list_tenants=ListTenants(self.tenants),
            issue_api_key=IssueApiKey(self.tenants, self.keys, self.clock),
            list_api_keys=ListApiKeys(self.keys),
            rotate_api_key=RotateApiKey(self.keys, self.clock, grace_seconds=3600),
            revoke_api_key=RevokeApiKey(self.keys, self.revocation_list, self.clock),
            validate_api_key=validate_api_key,
            validate_access_token=ValidateAccessTokenCredential(
                self.verifier, self.revocation_list, self.rate_limiter
            ),
            issue_access_token=IssueAccessToken(validate_api_key, self.signer, ttl_seconds=900),
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
        auth_jwt_secret=TEST_JWT_SECRET,
        auth_admin_token=TEST_ADMIN_TOKEN,
        # Point at nothing routable; /readyz is the only thing that would try.
        database_url="postgresql+psycopg://nobody:nothing@127.0.0.1:9/none",
        redis_url="redis://127.0.0.1:9/0",
    )
    app = build_app(settings=settings, unit_of_work_factory=unit_of_work)
    return TestClient(app)


ADMIN_HEADERS = {"X-Admin-Token": TEST_ADMIN_TOKEN}


def create_tenant(client: TestClient, name: str = "acme", plan_tier: str = "free") -> dict:
    response = client.post(
        "/admin/tenants", json={"name": name, "plan_tier": plan_tier}, headers=ADMIN_HEADERS
    )
    assert response.status_code == 201, response.text
    return response.json()


def issue_key(client: TestClient, tenant_id: str, **overrides) -> dict:
    response = client.post(
        f"/admin/tenants/{tenant_id}/api-keys", json=overrides, headers=ADMIN_HEADERS
    )
    assert response.status_code == 201, response.text
    return response.json()
