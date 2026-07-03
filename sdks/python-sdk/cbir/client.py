"""The CBIR client — a thin wrapper over the public REST API."""

from __future__ import annotations

import mimetypes
from pathlib import Path

import httpx

from cbir.errors import CBIRAPIError, CBIRAuthError
from cbir.models import CatalogItem, SearchResult


class CBIRClient:
    def __init__(
        self,
        api_key: str,
        catalog_url: str = "http://localhost:8002",
        query_url: str = "http://localhost:8004",
        timeout_seconds: float = 30.0,
    ) -> None:
        self._api_key = api_key
        self._catalog = httpx.Client(
            base_url=catalog_url.rstrip("/"),
            headers={"X-API-Key": api_key},
            timeout=timeout_seconds,
        )
        self._query = httpx.Client(
            base_url=query_url.rstrip("/"),
            headers={"X-API-Key": api_key},
            timeout=timeout_seconds,
        )

    # -- ingestion ------------------------------------------------------------

    def ingest_image(
        self,
        path: str | Path,
        metadata: dict | None = None,
        external_id: str | None = None,
    ) -> CatalogItem:
        """Register → upload bytes to the signed URL → confirm, in one call.
        Returns the item in its post-confirmation (queued) state; poll
        `get_item(...).status` until it becomes `indexed`."""
        path = Path(path)
        content_type = mimetypes.guess_type(path.name)[0] or "image/jpeg"
        registered = self._register(content_type, metadata, external_id)
        item = registered["item"]
        upload = registered["upload"]

        with open(path, "rb") as fh:
            data = fh.read()
        put = httpx.request(
            upload["method"], upload["url"], content=data, headers=upload["headers"]
        )
        if put.status_code not in (200, 204):
            raise CBIRAPIError(put.status_code, "object upload failed")

        confirmed = self._request(self._catalog, "POST", f"/v1/items/{item['id']}/confirm")
        return CatalogItem.from_api(confirmed)

    def get_item(self, item_id: str) -> CatalogItem:
        data = self._request(self._catalog, "GET", f"/v1/items/{item_id}")
        return CatalogItem.from_api(data["item"])

    def list_items(self, status: str | None = None, limit: int = 50) -> list[CatalogItem]:
        params = {"limit": limit}
        if status:
            params["status"] = status
        data = self._request(self._catalog, "GET", "/v1/items", params=params)
        return [CatalogItem.from_api(d) for d in data]

    def delete_item(self, item_id: str) -> None:
        self._request(self._catalog, "DELETE", f"/v1/items/{item_id}", expect_json=False)

    def submit_feedback(self, item_id: str, query_ref: str, relevant: bool) -> None:
        self._request(
            self._catalog,
            "POST",
            "/v1/feedback",
            json={"item_id": item_id, "query_ref": query_ref, "relevant": relevant},
        )

    # -- search ---------------------------------------------------------------

    def search_by_image(
        self, path: str | Path, top_k: int = 10, filters: dict | None = None
    ) -> list[SearchResult]:
        with open(Path(path), "rb") as fh:
            files = {"file": (Path(path).name, fh.read(), "application/octet-stream")}
        data = {"top_k": str(top_k)}
        if filters:
            import json

            data["filters"] = json.dumps(filters)
        payload = self._request(self._query, "POST", "/v1/search/image", files=files, data=data)
        return [SearchResult.from_api(r) for r in payload["results"]]

    def search_by_text(
        self, query: str, top_k: int = 10, filters: dict | None = None
    ) -> list[SearchResult]:
        body = {"query": query, "top_k": top_k, "filters": filters or {}}
        payload = self._request(self._query, "POST", "/v1/search/text", json=body)
        return [SearchResult.from_api(r) for r in payload["results"]]

    def search_composed(
        self, path: str | Path, modifier: str, top_k: int = 10, filters: dict | None = None
    ) -> list[SearchResult]:
        with open(Path(path), "rb") as fh:
            files = {"file": (Path(path).name, fh.read(), "application/octet-stream")}
        data = {"modifier": modifier, "top_k": str(top_k)}
        if filters:
            import json

            data["filters"] = json.dumps(filters)
        payload = self._request(self._query, "POST", "/v1/search/composed", files=files, data=data)
        return [SearchResult.from_api(r) for r in payload["results"]]

    # -- internals ------------------------------------------------------------

    def _register(self, content_type, metadata, external_id) -> dict:
        return self._request(
            self._catalog,
            "POST",
            "/v1/items",
            json={
                "content_type": content_type,
                "metadata": metadata or {},
                "external_id": external_id,
            },
        )

    def _request(self, client, method, path, expect_json=True, **kwargs) -> dict:
        try:
            response = client.request(method, path, **kwargs)
        except httpx.HTTPError as exc:
            raise CBIRAPIError(0, f"transport error: {exc}") from exc
        if response.status_code in (401, 403):
            raise CBIRAuthError(_detail(response))
        if response.status_code >= 400:
            raise CBIRAPIError(response.status_code, _detail(response))
        if not expect_json or not response.content:
            return {}
        return response.json()

    def close(self) -> None:
        self._catalog.close()
        self._query.close()

    def __enter__(self) -> CBIRClient:
        return self

    def __exit__(self, *exc) -> None:
        self.close()


def _detail(response: httpx.Response) -> str:
    try:
        return response.json().get("detail", response.text)
    except ValueError:
        return response.text
