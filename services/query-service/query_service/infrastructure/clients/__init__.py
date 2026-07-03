"""HTTP/vector-store adapters for query-service's ports."""

from __future__ import annotations

import base64

import httpx
from cbir_common.vectordb import VectorStore

from query_service.application.errors import EmbeddingServiceError, InvalidQueryError
from query_service.application.ports import (
    IndexHit,
    QueryEmbedderPort,
    RerankerPort,
    SearchIndexPort,
)


class AiServiceQueryEmbedder(QueryEmbedderPort):
    """Query-time single-item embedding via ai-service (the low-latency path,
    distinct from the worker's batched ingestion embedding)."""

    def __init__(self, base_url: str, timeout_seconds: float = 15.0) -> None:
        self._client = httpx.Client(base_url=base_url, timeout=timeout_seconds)

    def _embed_one(self, item: dict) -> list[float]:
        try:
            response = self._client.post("/internal/embed", json={"inputs": [item]})
        except httpx.HTTPError as exc:
            raise EmbeddingServiceError("embedding service unreachable") from exc
        if response.status_code == 422:
            raise InvalidQueryError(response.json().get("detail", "invalid query"))
        if response.status_code != 200:
            raise EmbeddingServiceError(f"embedding service returned {response.status_code}")
        return response.json()["results"][0]["vector"]

    def embed_image(self, image_bytes: bytes) -> list[float]:
        return self._embed_one(
            {"modality": "image", "image_base64": base64.b64encode(image_bytes).decode()}
        )

    def embed_text(self, text: str) -> list[float]:
        return self._embed_one({"modality": "text", "text": text})

    def reachable(self) -> bool:
        try:
            return self._client.get("/health").status_code == 200
        except httpx.HTTPError:
            return False


class VectorStoreSearchIndex(SearchIndexPort):
    """Adapts the shared VectorStore (Qdrant in prod, in-memory in tests) to
    query-service's SearchIndexPort."""

    def __init__(self, store: VectorStore) -> None:
        self._store = store

    def search(
        self,
        tenant_id: str,
        vector: list[float],
        limit: int,
        filters: dict | None,
        with_vectors: bool = False,
    ) -> list[IndexHit]:
        hits = self._store.search(
            tenant_id, vector, limit=limit, filters=filters, with_vectors=with_vectors
        )
        return [
            IndexHit(item_id=h.id, score=h.score, payload=h.payload, vector=h.vector) for h in hits
        ]

    def reachable(self) -> bool:
        return self._store.reachable()


class AiServiceReranker(RerankerPort):
    """Reranking via ai-service /internal/rerank (Milestone 9)."""

    def __init__(self, base_url: str, timeout_seconds: float = 15.0) -> None:
        self._client = httpx.Client(base_url=base_url, timeout=timeout_seconds)

    def rerank(
        self,
        query_vector: list[float],
        candidates: list[tuple[str, list[float]]],
        modifier_vector: list[float] | None,
        top_k: int,
    ) -> list[tuple[str, float]]:
        body = {
            "query_vector": query_vector,
            "candidates": [{"id": cid, "vector": vec} for cid, vec in candidates if vec],
            "modifier_vector": modifier_vector,
            "top_k": top_k,
        }
        if not body["candidates"]:
            # No candidate vectors to rerank with — preserve incoming order.
            return [(cid, 0.0) for cid, _ in candidates]
        try:
            response = self._client.post("/internal/rerank", json=body)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise EmbeddingServiceError("reranking service unreachable") from exc
        return [(item["id"], item["score"]) for item in response.json()["items"]]
