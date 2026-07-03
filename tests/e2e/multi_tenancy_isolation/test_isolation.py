"""Cross-service tenant-isolation journey (M2 acceptance criterion 3).

Verifies that tenant A's credential cannot reach tenant B's catalog data
under any tested path — spanning auth-service (validation) and
catalog-service (enforcement) together, which no single service's own test
suite can exercise.
"""

from __future__ import annotations

import httpx
from tests.e2e.conftest import CATALOG_URL


def _register_item(api_key: str) -> dict:
    return httpx.post(
        f"{CATALOG_URL}/v1/items",
        headers={"X-API-Key": api_key},
        json={"content_type": "image/jpeg", "metadata": {"category": "isolation"}},
    ).json()


def test_tenant_cannot_read_or_delete_another_tenants_item(new_tenant_with_key):
    _, key_a = new_tenant_with_key()
    _, key_b = new_tenant_with_key()

    item = _register_item(key_a)
    item_id = item["item"]["id"]

    # B cannot GET A's item.
    assert (
        httpx.get(f"{CATALOG_URL}/v1/items/{item_id}", headers={"X-API-Key": key_b}).status_code
        == 404
    )
    # B cannot DELETE A's item.
    assert (
        httpx.delete(f"{CATALOG_URL}/v1/items/{item_id}", headers={"X-API-Key": key_b}).status_code
        == 404
    )
    # B's listing does not include A's item.
    b_list = httpx.get(f"{CATALOG_URL}/v1/items", headers={"X-API-Key": key_b}).json()
    assert all(i["id"] != item_id for i in b_list)
    # A still sees its own item.
    assert (
        httpx.get(f"{CATALOG_URL}/v1/items/{item_id}", headers={"X-API-Key": key_a}).status_code
        == 200
    )


def test_read_only_key_cannot_write(new_tenant_with_key):
    _, ro_key = new_tenant_with_key(scopes=["catalog:read"])
    response = httpx.post(
        f"{CATALOG_URL}/v1/items",
        headers={"X-API-Key": ro_key},
        json={"content_type": "image/jpeg"},
    )
    assert response.status_code == 403


def test_invalid_key_rejected_at_catalog(new_tenant_with_key):
    response = httpx.get(f"{CATALOG_URL}/v1/items", headers={"X-API-Key": "cbir_bogus_key"})
    assert response.status_code == 401
