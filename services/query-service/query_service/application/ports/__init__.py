"""Ports the search use cases depend on. Concrete adapters (ai-service client,
Qdrant search, Redis cache, ai-service reranker) live in infrastructure/.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class IndexHit:
    item_id: str
    score: float
    payload: dict
    vector: list[float] | None = None  # populated only when with_vectors=True


class QueryEmbedderPort(ABC):
    @abstractmethod
    def embed_image(self, image_bytes: bytes) -> list[float]: ...

    @abstractmethod
    def embed_text(self, text: str) -> list[float]: ...


class SearchIndexPort(ABC):
    @abstractmethod
    def search(
        self,
        tenant_id: str,
        vector: list[float],
        limit: int,
        filters: dict | None,
        with_vectors: bool = False,
    ) -> list[IndexHit]: ...


class RerankerPort(ABC):
    """Optional post-ANN rerank stage (Milestone 9). Returns (item_id, score)
    pairs in the reranked order."""

    @abstractmethod
    def rerank(
        self,
        query_vector: list[float],
        candidates: list[tuple[str, list[float]]],
        modifier_vector: list[float] | None,
        top_k: int,
    ) -> list[tuple[str, float]]: ...


class QueryCachePort(ABC):
    """Query embedding + result cache (Milestone 8). Keys embed the tenant's
    index version so a re-index transparently invalidates stale entries."""

    @abstractmethod
    def index_version(self, tenant_id: str) -> str: ...

    @abstractmethod
    def get_results(self, key: str) -> list[dict] | None: ...

    @abstractmethod
    def set_results(self, key: str, results: list[dict], ttl_seconds: int) -> None: ...

    @abstractmethod
    def get_embedding(self, key: str) -> list[float] | None: ...

    @abstractmethod
    def set_embedding(self, key: str, vector: list[float], ttl_seconds: int) -> None: ...


class NullQueryCache(QueryCachePort):
    """No-op cache: every lookup misses. The default until Milestone 8 wires
    Redis, and the graceful-degradation fallback if Redis is unavailable."""

    def index_version(self, tenant_id: str) -> str:
        return "0"

    def get_results(self, key: str) -> list[dict] | None:
        return None

    def set_results(self, key: str, results: list[dict], ttl_seconds: int) -> None:
        pass

    def get_embedding(self, key: str) -> list[float] | None:
        return None

    def set_embedding(self, key: str, vector: list[float], ttl_seconds: int) -> None:
        pass
