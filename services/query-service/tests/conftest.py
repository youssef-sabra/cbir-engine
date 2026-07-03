"""In-memory fakes for query-service tests: a fake embedder mapping known
inputs to known vectors, the shared InMemoryVectorStore as the search index,
and a real in-memory cache so caching + invalidation are actually exercised."""

from __future__ import annotations

import uuid
from contextlib import contextmanager

import pytest
from cbir_common.auth import TenantContext
from cbir_common.vectordb import InMemoryVectorStore, VectorRecord
from fastapi.testclient import TestClient

from query_service.application.ports import (
    IndexHit,
    QueryCachePort,
    QueryEmbedderPort,
    RerankerPort,
    SearchIndexPort,
)
from query_service.application.use_cases.bundle import UseCaseBundle
from query_service.application.use_cases.search import SearchService
from query_service.entrypoint.composition_root import build_app
from query_service.infrastructure.config import Settings


class FakeEmbedder(QueryEmbedderPort):
    """Maps registered inputs to vectors; unknown text hashes to a vector so
    arbitrary queries still work."""

    def __init__(self) -> None:
        self.images: dict[bytes, list[float]] = {}
        self.texts: dict[str, list[float]] = {}
        self.image_calls = 0
        self.text_calls = 0

    def embed_image(self, image_bytes: bytes) -> list[float]:
        self.image_calls += 1
        return self.images.get(image_bytes, [0.0, 0.0, 1.0])

    def embed_text(self, text: str) -> list[float]:
        self.text_calls += 1
        return self.texts.get(text, [0.0, 1.0, 0.0])


class StoreSearchIndex(SearchIndexPort):
    def __init__(self, store: InMemoryVectorStore) -> None:
        self.store = store
        self.searches = 0

    def search(self, tenant_id, vector, limit, filters, with_vectors=False):
        self.searches += 1
        hits = self.store.search(tenant_id, vector, limit, filters, with_vectors=with_vectors)
        return [IndexHit(h.id, h.score, h.payload, h.vector) for h in hits]


class DictCache(QueryCachePort):
    """A real (in-process) cache with a per-tenant index version, so cache-hit
    and invalidation-on-reindex behaviour is genuinely tested."""

    def __init__(self) -> None:
        self.results: dict[str, list[dict]] = {}
        self.embeddings: dict[str, list[float]] = {}
        self.versions: dict[str, int] = {}

    def bump(self, tenant_id: str) -> None:
        self.versions[tenant_id] = self.versions.get(tenant_id, 0) + 1

    def index_version(self, tenant_id: str) -> str:
        return str(self.versions.get(tenant_id, 0))

    def get_results(self, key):
        return self.results.get(key)

    def set_results(self, key, results, ttl_seconds):
        self.results[key] = results

    def get_embedding(self, key):
        return self.embeddings.get(key)

    def set_embedding(self, key, vector, ttl_seconds):
        self.embeddings[key] = vector


class PassthroughReranker(RerankerPort):
    """Cosine-blend reranker mirror for tests (no ai-service needed)."""

    def rerank(self, query_vector, candidates, modifier_vector, top_k):
        import math

        def unit(v):
            n = math.sqrt(sum(x * x for x in v)) or 1.0
            return [x / n for x in v]

        q = unit(query_vector)
        mod = unit(modifier_vector) if modifier_vector else None
        out = []
        for cid, vec in candidates:
            if not vec:
                out.append((cid, 0.0))
                continue
            c = unit(vec)
            score = sum(a * b for a, b in zip(q, c, strict=False))
            if mod:
                score = 0.5 * score + 0.5 * sum(a * b for a, b in zip(mod, c, strict=False))
            out.append((cid, score))
        out.sort(key=lambda p: p[1], reverse=True)
        return out[:top_k]


class SwitchableAuth:
    def __init__(self) -> None:
        self.tenant_id = str(uuid.uuid4())
        self.scopes = ["search:query"]

    def __call__(self) -> TenantContext:
        return TenantContext(
            tenant_id=self.tenant_id,
            api_key_id=str(uuid.uuid4()),
            scopes=self.scopes,
            plan_tier="free",
        )


class World:
    def __init__(self, with_reranker: bool = True) -> None:
        self.embedder = FakeEmbedder()
        self.store = InMemoryVectorStore()
        self.index = StoreSearchIndex(self.store)
        self.cache = DictCache()
        self.reranker = PassthroughReranker() if with_reranker else None
        self.auth = SwitchableAuth()

    def service(self) -> SearchService:
        return SearchService(self.embedder, self.index, self.cache, reranker=self.reranker)

    def index_item(self, tenant, item_id, vector, payload=None):
        self.store.ensure_collection(tenant, dim=len(vector))
        self.store.upsert(tenant, [VectorRecord(item_id, vector, payload or {})])


@pytest.fixture
def world() -> World:
    return World()


@pytest.fixture
def client(world: World) -> TestClient:
    @contextmanager
    def uow():
        yield UseCaseBundle(search=world.service())

    settings = Settings(enable_cache=False)
    app = build_app(settings=settings, unit_of_work_factory=uow, require_query=world.auth)
    return TestClient(app)
