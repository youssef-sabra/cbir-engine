"""Composition root for ai-service: select the encoder + reranker by config
and wire the use cases into a stateless FastAPI app."""

from __future__ import annotations

from cbir_common.structured_logging import configure_logging
from fastapi import FastAPI

from ai_service.application.use_cases.bundle import UseCaseBundle
from ai_service.application.use_cases.embeddings import GenerateEmbeddings
from ai_service.application.use_cases.reranking import RerankShortlist
from ai_service.infrastructure.config import Settings
from ai_service.infrastructure.embedding import build_embedding_provider
from ai_service.infrastructure.reranking import CosineBlendReranker
from ai_service.interface_adapters.controllers import (
    build_internal_router,
    register_error_handlers,
)


def build_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    configure_logging(settings.service_name)

    provider = build_embedding_provider(
        settings.embedding_provider,
        checkpoint=settings.embedding_model_checkpoint,
        pretrained=settings.embedding_model_pretrained,
        device=settings.embedding_device,
    )
    use_cases = UseCaseBundle(
        generate_embeddings=GenerateEmbeddings(provider),
        rerank_shortlist=RerankShortlist(CosineBlendReranker()),
    )

    app = FastAPI(
        title=settings.service_name,
        version=settings.service_version,
        description="Embedding generation and reranking (pluggable encoder).",
    )
    register_error_handlers(app)
    app.include_router(build_internal_router(use_cases))

    @app.get("/health", tags=["ops"])
    def health() -> dict:
        return {
            "status": "ok",
            "service": settings.service_name,
            "version": settings.service_version,
            "embedding_provider": settings.embedding_provider,
            "model_version": provider.model_version,
        }

    @app.get("/readyz", tags=["ops"])
    def readyz() -> dict:
        # Stateless: if the encoder loaded (constructor ran), the service is
        # ready. A real GPU model would additionally check weights are loaded.
        return {
            "status": "ok",
            "service": settings.service_name,
            "embedding_dim": provider.embedding_dim,
        }

    return app
