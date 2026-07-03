"""SDK unit tests using httpx's MockTransport — no live stack required. They
pin the SDK's HTTP contract: correct paths, auth header, the upload handshake,
and error translation."""

from __future__ import annotations

import json

import httpx
import pytest

from cbir import CBIRAPIError, CBIRAuthError, CBIRClient


class FakeBackend:
    """Records requests and serves canned responses for the catalog + query
    APIs, plus the object-storage PUT."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def catalog(self, request: httpx.Request) -> httpx.Response:
        self.calls.append((request.method, request.url.path))
        assert request.headers.get("X-API-Key") == "cbir_test"
        p = request.url.path
        if request.method == "POST" and p == "/v1/items":
            return httpx.Response(
                201,
                json={
                    "item": {
                        "id": "item-1",
                        "status": "pending_upload",
                        "content_type": "image/jpeg",
                        "metadata": {"category": "shoes"},
                        "external_id": None,
                        "size_bytes": None,
                    },
                    "upload": {
                        "url": "https://storage.local/put/item-1",
                        "method": "PUT",
                        "headers": {"Content-Type": "image/jpeg"},
                        "expires_in_seconds": 900,
                    },
                },
            )
        if request.method == "POST" and p == "/v1/items/item-1/confirm":
            return httpx.Response(
                200,
                json={
                    "id": "item-1",
                    "status": "queued",
                    "content_type": "image/jpeg",
                    "metadata": {"category": "shoes"},
                    "external_id": None,
                    "size_bytes": 2048,
                },
            )
        if request.method == "POST" and p == "/v1/feedback":
            return httpx.Response(201, json={"id": "fb-1", "status": "recorded"})
        if request.method == "DELETE":
            return httpx.Response(204)
        return httpx.Response(404, json={"detail": "not found"})

    def query(self, request: httpx.Request) -> httpx.Response:
        self.calls.append((request.method, request.url.path))
        if request.url.path == "/v1/search/text":
            body = json.loads(request.content)
            assert body["query"] == "red shoes"
            return httpx.Response(
                200,
                json={
                    "results": [{"item_id": "item-1", "score": 0.9, "metadata": {}}],
                    "count": 1,
                    "cached": False,
                    "reranked": False,
                },
            )
        if request.url.path == "/v1/search/image":
            return httpx.Response(
                200,
                json={
                    "results": [{"item_id": "item-1", "score": 0.8, "metadata": {}}],
                    "count": 1,
                    "cached": False,
                    "reranked": False,
                },
            )
        return httpx.Response(404, json={"detail": "not found"})


def _client(backend: FakeBackend) -> CBIRClient:
    client = CBIRClient(api_key="cbir_test")
    client._catalog = httpx.Client(
        base_url="http://catalog",
        headers={"X-API-Key": "cbir_test"},
        transport=httpx.MockTransport(backend.catalog),
    )
    client._query = httpx.Client(
        base_url="http://query",
        headers={"X-API-Key": "cbir_test"},
        transport=httpx.MockTransport(backend.query),
    )
    return client


def test_ingest_image_does_register_upload_confirm(tmp_path, monkeypatch):
    backend = FakeBackend()
    client = _client(backend)

    # capture the signed-URL PUT
    puts = []

    def fake_request(method, url, **kwargs):
        puts.append((method, url))
        return httpx.Response(200)

    monkeypatch.setattr(httpx, "request", fake_request)

    img = tmp_path / "shoe.jpg"
    img.write_bytes(b"fake-bytes")
    item = client.ingest_image(img, metadata={"category": "shoes"})

    assert item.id == "item-1"
    assert item.status == "queued"
    assert item.size_bytes == 2048
    assert puts == [("PUT", "https://storage.local/put/item-1")]
    assert ("POST", "/v1/items") in backend.calls
    assert ("POST", "/v1/items/item-1/confirm") in backend.calls


def test_search_by_text(monkeypatch):
    backend = FakeBackend()
    client = _client(backend)
    results = client.search_by_text("red shoes", top_k=3)
    assert len(results) == 1
    assert results[0].item_id == "item-1"
    assert results[0].score == 0.9


def test_search_by_image(tmp_path):
    backend = FakeBackend()
    client = _client(backend)
    img = tmp_path / "q.jpg"
    img.write_bytes(b"q")
    results = client.search_by_image(img, top_k=5, filters={"category": "shoes"})
    assert results[0].item_id == "item-1"


def test_feedback(monkeypatch):
    backend = FakeBackend()
    client = _client(backend)
    client.submit_feedback("item-1", "q-1", relevant=True)
    assert ("POST", "/v1/feedback") in backend.calls


def test_auth_error_translation():
    def unauthorized(request):
        return httpx.Response(401, json={"detail": "invalid API key"})

    client = CBIRClient(api_key="bad")
    client._catalog = httpx.Client(base_url="http://c", transport=httpx.MockTransport(unauthorized))
    with pytest.raises(CBIRAuthError):
        client.get_item("x")


def test_api_error_carries_detail():
    def boom(request):
        return httpx.Response(422, json={"detail": "unsupported content type"})

    client = CBIRClient(api_key="k")
    client._catalog = httpx.Client(base_url="http://c", transport=httpx.MockTransport(boom))
    with pytest.raises(CBIRAPIError) as exc:
        client.get_item("x")
    assert exc.value.status_code == 422
    assert "unsupported" in exc.value.detail
