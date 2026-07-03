"""API tests for query-service: multipart image search, JSON text search,
compositional search, validation, and scope enforcement."""

from __future__ import annotations

import io


def _seed(world, tenant="t1"):
    world.auth.tenant_id = tenant
    world.embedder.images[b"queryimg"] = [1.0, 0.0, 0.0]
    world.embedder.texts["red shoes"] = [1.0, 0.0, 0.0]
    world.index_item(tenant, "near", [0.95, 0.05, 0.0], {"category": "shoes"})
    world.index_item(tenant, "far", [0.0, 1.0, 0.0], {"category": "bags"})


def _img(data=b"queryimg"):
    return {"file": ("q.jpg", io.BytesIO(data), "image/jpeg")}


class TestImageSearch:
    def test_returns_ranked_results(self, client, world):
        _seed(world)
        r = client.post("/v1/search/image", files=_img(), data={"top_k": 5})
        assert r.status_code == 200
        body = r.json()
        assert body["results"][0]["item_id"] == "near"
        assert body["count"] == 2
        assert "score" in body["results"][0]

    def test_hybrid_filter(self, client, world):
        _seed(world)
        r = client.post("/v1/search/image", files=_img(), data={"filters": '{"category": "bags"}'})
        assert [x["item_id"] for x in r.json()["results"]] == ["far"]

    def test_empty_upload_rejected(self, client, world):
        _seed(world)
        r = client.post(
            "/v1/search/image", files={"file": ("q.jpg", io.BytesIO(b""), "image/jpeg")}
        )
        assert r.status_code == 422

    def test_bad_filters_json_rejected(self, client, world):
        _seed(world)
        r = client.post("/v1/search/image", files=_img(), data={"filters": "not json"})
        assert r.status_code == 422

    def test_top_k_out_of_range_rejected(self, client, world):
        _seed(world)
        r = client.post("/v1/search/image", files=_img(), data={"top_k": 9999})
        assert r.status_code == 422


class TestTextSearch:
    def test_text_query(self, client, world):
        _seed(world)
        r = client.post("/v1/search/text", json={"query": "red shoes", "top_k": 3})
        assert r.status_code == 200
        assert r.json()["results"][0]["item_id"] == "near"

    def test_empty_query_rejected(self, client, world):
        _seed(world)
        assert client.post("/v1/search/text", json={"query": ""}).status_code == 422


class TestComposedSearch:
    def test_composed_reranks(self, client, world):
        world.auth.tenant_id = "t1"
        world.embedder.images[b"ref"] = [1.0, 0.0, 0.0]
        world.embedder.texts["in blue"] = [0.0, 0.0, 1.0]
        world.index_item("t1", "red", [1.0, 0.0, 0.0])
        world.index_item("t1", "blue", [0.5, 0.0, 0.87])
        r = client.post(
            "/v1/search/composed",
            files={"file": ("r.jpg", io.BytesIO(b"ref"), "image/jpeg")},
            data={"modifier": "in blue"},
        )
        assert r.status_code == 200
        assert r.json()["reranked"] is True
        assert r.json()["results"][0]["item_id"] == "blue"


# Note: scope enforcement (search:query) lives in cbir_common's gateway-role
# dependency, not in query-service itself; it is covered by that package and by
# the live cross-service e2e (a read-only key -> 403). The unit tests here
# inject the auth dependency directly, so they don't re-test that seam.


class TestOps:
    def test_health(self, client):
        assert client.get("/health").json()["status"] == "ok"
