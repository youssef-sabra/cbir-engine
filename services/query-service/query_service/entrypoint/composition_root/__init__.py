"""Composition root for query-service.

Tests inject `unit_of_work_factory` (in-memory index + fake embedder + null
cache) and `require_query`; production wiring uses ai-service, Qdrant, and
the Redis cache, with gateway-role auth via auth-service.
"""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager, contextmanager
from typing import Any

from cbir_common.auth import AuthServiceClient, build_scope_dependency
from cbir_common.structured_logging import configure_logging
from fastapi import FastAPI, Response, status

from query_service.application.ports import NullQueryCache
from query_service.application.use_cases.bundle import UseCaseBundle
from query_service.application.use_cases.search import SearchService
from query_service.infrastructure.config import Settings
from query_service.interface_adapters.controllers import (
    build_search_router,
    register_error_handlers,
)

UnitOfWorkFactory = Callable[[], AbstractContextManager[UseCaseBundle]]


def build_app(
    settings: Settings | None = None,
    unit_of_work_factory: UnitOfWorkFactory | None = None,
    require_query: Callable[..., Any] | None = None,
) -> FastAPI:
    settings = settings or Settings()
    configure_logging(settings.service_name)

    embedder = None
    index = None
    cache_client = None
    auth_client = None

    if unit_of_work_factory is None:
        import redis
        from cbir_common.vectordb import QdrantVectorStore

        from query_service.infrastructure.cache import RedisQueryCache
        from query_service.infrastructure.clients import (
            AiServiceQueryEmbedder,
            AiServiceReranker,
            VectorStoreSearchIndex,
        )

        embedder = AiServiceQueryEmbedder(settings.ai_service_url)
        index = VectorStoreSearchIndex(QdrantVectorStore(settings.qdrant_url))
        reranker = AiServiceReranker(settings.ai_service_url)
        if settings.enable_cache:
            cache_client = RedisQueryCache(redis.Redis.from_url(settings.redis_url))
            cache = cache_client
        else:
            cache = NullQueryCache()
        service = SearchService(embedder, index, cache, reranker=reranker)

        @contextmanager
        def sql_unit_of_work():
            yield UseCaseBundle(search=service)

        unit_of_work_factory = sql_unit_of_work

    if require_query is None:
        auth_client = AuthServiceClient(settings.auth_service_url)
        require_query = build_scope_dependency(auth_client, "search:query")

    app = FastAPI(
        title=settings.service_name,
        version=settings.service_version,
        description="Image, text, and compositional search over indexed catalogs.",
    )
    register_error_handlers(app)
    app.include_router(build_search_router(unit_of_work_factory, require_query))

    @app.get("/health", tags=["ops"])
    def health() -> dict:
        return {
            "status": "ok",
            "service": settings.service_name,
            "version": settings.service_version,
        }

    @app.get("/readyz", tags=["ops"])
    def readyz(response: Response) -> dict:
        results = {}
        if embedder is not None:
            results["ai_service"] = {"reachable": embedder.reachable()}
        if index is not None:
            results["vector_db"] = {"reachable": index.reachable()}
        if cache_client is not None:
            results["cache"] = {"reachable": cache_client.reachable()}
        if auth_client is not None:
            results["auth_service"] = {"reachable": auth_client.health_reachable()}
        all_ok = all(r["reachable"] for r in results.values()) if results else True
        if not all_ok:
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {
            "status": "ok" if all_ok else "degraded",
            "service": settings.service_name,
            "dependencies": results,
        }

    return app
