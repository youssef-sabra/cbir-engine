"""API tests for ai-service: batched embed, phash, rerank, error handling."""

from __future__ import annotations

from tests.conftest import make_image_b64


class TestEmbed:
    def test_batched_mixed_modalities_preserve_order(self, client):
        body = {
            "inputs": [
                {"modality": "image", "image_base64": make_image_b64((200, 20, 20))},
                {"modality": "text", "text": "a caption"},
                {"modality": "image", "image_base64": make_image_b64((20, 20, 200))},
            ],
            "include_phash": True,
        }
        r = client.post("/internal/embed", json=body)
        assert r.status_code == 200
        data = r.json()
        assert data["model_version"] == "local-hash-v1"
        assert data["embedding_dim"] == 512
        assert len(data["results"]) == 3
        # phash present for images, absent for text
        assert data["results"][0]["phash"] is not None
        assert data["results"][1]["phash"] is None
        assert data["results"][2]["phash"] is not None
        assert len(data["results"][0]["vector"]) == 512

    def test_phash_omitted_when_not_requested(self, client):
        body = {"inputs": [{"modality": "image", "image_base64": make_image_b64((1, 2, 3))}]}
        r = client.post("/internal/embed", json=body)
        assert r.json()["results"][0]["phash"] is None

    def test_invalid_base64_is_422(self, client):
        body = {"inputs": [{"modality": "image", "image_base64": "not base64!!!"}]}
        assert client.post("/internal/embed", json=body).status_code == 422

    def test_non_image_bytes_is_422(self, client):
        import base64

        junk = base64.b64encode(b"this is not an image").decode()
        body = {"inputs": [{"modality": "image", "image_base64": junk}]}
        assert client.post("/internal/embed", json=body).status_code == 422

    def test_empty_inputs_rejected_by_schema(self, client):
        assert client.post("/internal/embed", json={"inputs": []}).status_code == 422


class TestRerank:
    def _vec(self, client, b64):
        r = client.post(
            "/internal/embed",
            json={"inputs": [{"modality": "image", "image_base64": b64}]},
        )
        return r.json()["results"][0]["vector"]

    def test_rerank_orders_by_similarity_to_query(self, client):
        query = self._vec(client, make_image_b64((220, 20, 20)))
        near = self._vec(client, make_image_b64((210, 30, 30)))
        far = self._vec(client, make_image_b64((20, 20, 220)))
        body = {
            "query_vector": query,
            "candidates": [{"id": "far", "vector": far}, {"id": "near", "vector": near}],
        }
        r = client.post("/internal/rerank", json=body)
        assert r.status_code == 200
        items = r.json()["items"]
        assert items[0]["id"] == "near"  # closer color ranks first
        assert items[0]["score"] >= items[1]["score"]

    def test_compositional_modifier_shifts_ranking(self, client):
        red = self._vec(client, make_image_b64((220, 20, 20)))
        blue = self._vec(client, make_image_b64((20, 20, 220)))
        # Query is red; modifier is blue with full weight -> blue should win.
        body = {
            "query_vector": red,
            "candidates": [{"id": "red", "vector": red}, {"id": "blue", "vector": blue}],
            "modifier_vector": blue,
            "modifier_weight": 1.0,
        }
        items = client.post("/internal/rerank", json=body).json()["items"]
        assert items[0]["id"] == "blue"

    def test_top_k_truncates(self, client):
        v = self._vec(client, make_image_b64((100, 100, 100)))
        body = {
            "query_vector": v,
            "candidates": [{"id": str(i), "vector": v} for i in range(5)],
            "top_k": 2,
        }
        assert len(client.post("/internal/rerank", json=body).json()["items"]) == 2


class TestOps:
    def test_health_reports_provider(self, client):
        data = client.get("/health").json()
        assert data["status"] == "ok"
        assert data["embedding_provider"] == "local"
        assert data["model_version"] == "local-hash-v1"

    def test_readyz(self, client):
        assert client.get("/readyz").json()["embedding_dim"] == 512
