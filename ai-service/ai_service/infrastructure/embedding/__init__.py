"""Concrete embedding providers.

`build_embedding_provider` is the factory the composition root calls. The
default `LocalDeterministicEmbedder` is CPU-only and needs no model download,
so the whole platform runs locally and in CI; the SigLIP 2 / DINOv2 adapters
are the swap-in path for real semantic quality (NFR16).
"""

from __future__ import annotations

from ai_service.application.ports import EmbeddingProviderPort
from ai_service.infrastructure.embedding.local_embedder import (
    LOCAL_EMBEDDING_DIM,
    LocalDeterministicEmbedder,
)
from ai_service.infrastructure.embedding.model_adapters import DinoV2Embedder, SigLIP2Embedder

__all__ = [
    "EmbeddingProviderPort",
    "LocalDeterministicEmbedder",
    "LOCAL_EMBEDDING_DIM",
    "build_embedding_provider",
]


def build_embedding_provider(name: str) -> EmbeddingProviderPort:
    providers = {
        "local": LocalDeterministicEmbedder,
        "siglip2": SigLIP2Embedder,
        "dinov2": DinoV2Embedder,
    }
    try:
        return providers[name]()
    except KeyError:
        raise ValueError(
            f"unknown embedding provider '{name}'; known: {sorted(providers)}"
        ) from None
