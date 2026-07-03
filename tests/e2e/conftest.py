"""Shared fixtures for cross-service end-to-end tests.

These run against a LIVE Docker Compose stack (`docker compose up`), unlike
each service's own unit tests which use in-memory fakes. If the stack isn't
reachable, every e2e test is skipped rather than failed — so `pytest` stays
green on a machine that simply hasn't started the stack.

    docker compose up -d
    pip install -r tests/e2e/requirements-dev.txt
    pytest tests/e2e -v
"""

from __future__ import annotations

import os
import uuid

import httpx
import pytest

AUTH_URL = os.environ.get("E2E_AUTH_URL", "http://localhost:8001")
CATALOG_URL = os.environ.get("E2E_CATALOG_URL", "http://localhost:8002")
ADMIN_TOKEN = os.environ.get("AUTH_ADMIN_TOKEN", "local-dev-admin-token")


def _stack_up() -> bool:
    for url in (f"{AUTH_URL}/health", f"{CATALOG_URL}/health"):
        try:
            if httpx.get(url, timeout=2).status_code != 200:
                return False
        except httpx.HTTPError:
            return False
    return True


pytestmark = pytest.mark.skipif(
    not _stack_up(),
    reason="live Compose stack not reachable on :8001/:8002 — run `docker compose up -d`",
)


@pytest.fixture
def admin_headers() -> dict:
    return {"X-Admin-Token": ADMIN_TOKEN}


@pytest.fixture
def new_tenant_with_key(admin_headers):
    """Factory: create a uniquely-named tenant and issue an API key, returning
    (tenant_dict, full_api_key). Uniqueness avoids collisions across reruns."""

    def _make(plan_tier: str = "free", scopes: list[str] | None = None):
        name = f"e2e-{uuid.uuid4().hex[:12]}"
        tenant = httpx.post(
            f"{AUTH_URL}/admin/tenants",
            headers=admin_headers,
            json={"name": name, "plan_tier": plan_tier},
        ).json()
        body: dict = {"name": "e2e-key"}
        if scopes is not None:
            body["scopes"] = scopes
        issued = httpx.post(
            f"{AUTH_URL}/admin/tenants/{tenant['id']}/api-keys",
            headers=admin_headers,
            json=body,
        ).json()
        return tenant, issued["api_key"]

    return _make
