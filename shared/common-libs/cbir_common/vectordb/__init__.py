"""Vector-store client shared by the ingestion worker and query-service.

A technical utility with no business logic (fits `shared/`, per
docs/CLEAN_ARCHITECTURE.md Section 5): "put these vectors in a tenant's
collection", "find nearest neighbours with an optional metadata filter",
"delete these ids". The Qdrant implementation is the production path; an
in-memory implementation backs unit tests and needs no running Qdrant.

Per-tenant collections give native tenant isolation at the vector layer
(FR4.1) — a query can only ever touch one tenant's collection.

`qdrant_client` is imported lazily inside `QdrantVectorStore` so services that
don't do vector search (auth-service, catalog-service) never need it
installed.
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


def collection_name(tenant_id: str) -> str:
    """Deterministic per-tenant collection name. Hex-only so it satisfies
    Qdrant's collection-name constraints regardless of tenant id formatting."""
    return "tenant_" + tenant_id.replace("-", "")


@dataclass(frozen=True)
class VectorRecord:
    id: str  # the catalog item id — also the point id, so delete-by-item is trivial
    vector: list[float]
    payload: dict = field(default_factory=dict)


@dataclass(frozen=True)
class SearchHit:
    id: str
    score: float
    payload: dict
    vector: list[float] | None = None  # populated only when with_vectors=True


class VectorStore(ABC):
    @abstractmethod
    def ensure_collection(self, tenant_id: str, dim: int) -> None: ...

    @abstractmethod
    def upsert(self, tenant_id: str, records: list[VectorRecord]) -> None: ...

    @abstractmethod
    def search(
        self,
        tenant_id: str,
        vector: list[float],
        limit: int,
        filters: dict | None = None,
        with_vectors: bool = False,
    ) -> list[SearchHit]: ...

    @abstractmethod
    def delete(self, tenant_id: str, ids: list[str]) -> None: ...

    @abstractmethod
    def count(self, tenant_id: str) -> int: ...

    @abstractmethod
    def reachable(self) -> bool: ...


class InMemoryVectorStore(VectorStore):
    """Cosine-similarity store with equality metadata filtering. Behaviourally
    matches QdrantVectorStore's contract for tests and local fallback."""

    def __init__(self) -> None:
        self._collections: dict[str, dict[str, VectorRecord]] = {}

    def ensure_collection(self, tenant_id: str, dim: int) -> None:
        self._collections.setdefault(collection_name(tenant_id), {})

    def upsert(self, tenant_id: str, records: list[VectorRecord]) -> None:
        col = self._collections.setdefault(collection_name(tenant_id), {})
        for record in records:
            col[record.id] = record

    def search(
        self,
        tenant_id: str,
        vector: list[float],
        limit: int,
        filters: dict | None = None,
        with_vectors: bool = False,
    ) -> list[SearchHit]:
        col = self._collections.get(collection_name(tenant_id), {})
        hits = []
        for record in col.values():
            if filters and not _matches(record.payload, filters):
                continue
            hits.append(
                SearchHit(
                    record.id,
                    _cosine(vector, record.vector),
                    record.payload,
                    vector=list(record.vector) if with_vectors else None,
                )
            )
        hits.sort(key=lambda h: h.score, reverse=True)
        return hits[:limit]

    def delete(self, tenant_id: str, ids: list[str]) -> None:
        col = self._collections.get(collection_name(tenant_id))
        if col:
            for i in ids:
                col.pop(i, None)

    def count(self, tenant_id: str) -> int:
        return len(self._collections.get(collection_name(tenant_id), {}))

    def reachable(self) -> bool:
        return True


def _matches(payload: dict, filters: dict) -> bool:
    return all(payload.get(k) == v for k, v in filters.items())


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


class QdrantVectorStore(VectorStore):
    """Production vector store. Lazily imports qdrant_client so this module
    imports cleanly in services that never construct it."""

    def __init__(self, url: str, timeout_seconds: float = 10.0) -> None:
        from qdrant_client import QdrantClient

        self._client = QdrantClient(url=url, timeout=timeout_seconds)
        self._ensured: set[str] = set()

    def ensure_collection(self, tenant_id: str, dim: int) -> None:
        from qdrant_client.models import Distance, VectorParams

        name = collection_name(tenant_id)
        if name in self._ensured:
            return
        if not self._client.collection_exists(name):
            self._client.create_collection(
                collection_name=name,
                vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
            )
        self._ensured.add(name)

    def upsert(self, tenant_id: str, records: list[VectorRecord]) -> None:
        from qdrant_client.models import PointStruct

        name = collection_name(tenant_id)
        points = [PointStruct(id=r.id, vector=r.vector, payload=r.payload) for r in records]
        self._client.upsert(collection_name=name, points=points)

    def search(
        self,
        tenant_id: str,
        vector: list[float],
        limit: int,
        filters: dict | None = None,
        with_vectors: bool = False,
    ) -> list[SearchHit]:
        name = collection_name(tenant_id)
        query_filter = _build_qdrant_filter(filters)
        response = self._client.query_points(
            collection_name=name,
            query=vector,
            limit=limit,
            query_filter=query_filter,
            with_payload=True,
            with_vectors=with_vectors,
        )
        return [
            SearchHit(
                id=str(p.id),
                score=float(p.score),
                payload=p.payload or {},
                vector=list(p.vector) if (with_vectors and p.vector is not None) else None,
            )
            for p in response.points
        ]

    def delete(self, tenant_id: str, ids: list[str]) -> None:
        from qdrant_client.models import PointIdsList

        name = collection_name(tenant_id)
        self._client.delete(collection_name=name, points_selector=PointIdsList(points=list(ids)))

    def count(self, tenant_id: str) -> int:
        name = collection_name(tenant_id)
        if not self._client.collection_exists(name):
            return 0
        return int(self._client.count(collection_name=name).count)

    def reachable(self) -> bool:
        try:
            self._client.get_collections()
            return True
        except Exception:
            return False


def _build_qdrant_filter(filters: dict | None):
    if not filters:
        return None
    from qdrant_client.models import FieldCondition, Filter, MatchValue

    return Filter(
        must=[FieldCondition(key=k, match=MatchValue(value=v)) for k, v in filters.items()]
    )
