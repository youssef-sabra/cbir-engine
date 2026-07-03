"""End-to-end storage round trip (M3 acceptance criteria 1 & 3).

register -> PUT bytes to the signed URL -> confirm -> download the same
bytes -> delete (erasure) -> object and metadata both gone. Spans
catalog-service and MinIO. (Named ingestion_to_search per the planned test
layout; the embed/search half arrives with Milestones 5-7.)
"""

from __future__ import annotations

import httpx
from tests.e2e.conftest import CATALOG_URL

PAYLOAD = bytes(range(256)) * 8  # 2048 deterministic bytes


def test_signed_url_upload_confirm_download_then_erase(new_tenant_with_key):
    _, key = new_tenant_with_key()
    headers = {"X-API-Key": key}

    # Register -> pending_upload + signed PUT URL.
    registered = httpx.post(
        f"{CATALOG_URL}/v1/items",
        headers=headers,
        json={"content_type": "image/jpeg", "metadata": {"sku": "e2e-1"}},
    ).json()
    item_id = registered["item"]["id"]
    assert registered["item"]["status"] == "pending_upload"

    # Upload bytes directly to object storage via the signed URL.
    upload = registered["upload"]
    put = httpx.request(upload["method"], upload["url"], content=PAYLOAD, headers=upload["headers"])
    assert put.status_code in (200, 204)

    # Confirm -> uploaded, size persisted.
    confirmed = httpx.post(f"{CATALOG_URL}/v1/items/{item_id}/confirm", headers=headers).json()
    assert confirmed["status"] == "uploaded"
    assert confirmed["size_bytes"] == len(PAYLOAD)

    # Download via signed URL returns the exact bytes.
    got = httpx.get(f"{CATALOG_URL}/v1/items/{item_id}", headers=headers).json()
    download_url = got["download_url"]
    assert download_url is not None
    downloaded = httpx.get(download_url)
    assert downloaded.content == PAYLOAD

    # Erasure: delete removes both the object and the metadata row.
    assert httpx.delete(f"{CATALOG_URL}/v1/items/{item_id}", headers=headers).status_code == 204
    assert httpx.get(f"{CATALOG_URL}/v1/items/{item_id}", headers=headers).status_code == 404
    # The previously valid signed download URL now points at nothing.
    assert httpx.get(download_url).status_code in (403, 404)
