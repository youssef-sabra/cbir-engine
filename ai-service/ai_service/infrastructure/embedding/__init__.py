"""Concrete embedding providers and the factory the composition root calls.

Providers:
- `local`   — deterministic CPU embedder; no torch, no download. The offline /
  CI fallback (and the default), NOT the quality path.
- `siglip2` — SigLIP 2, the recommended production encoder (shared image/text
  space, multilingual).
- `openclip`— OpenCLIP alternative.
- `dinov2`  — image-only structural encoder.

The real models pull weights from the Hugging Face hub on first load; select
one with EMBEDDING_PROVIDER and (optionally) EMBEDDING_MODEL_CHECKPOINT.
"""

from __future__ import annotations

from ai_service.application.ports import EmbeddingProviderPort
from ai_service.infrastructure.embedding.local_embedder import (
    LOCAL_EMBEDDING_DIM,
    LocalDeterministicEmbedder,
)
from ai_service.infrastructure.embedding.model_adapters import (
    DinoV2Embedder,
    OpenClipEmbedder,
    SigLIP2Embedder,
)

__all__ = [
    "EmbeddingProviderPort",
    "LocalDeterministicEmbedder",
    "LOCAL_EMBEDDING_DIM",
    "build_embedding_provider",
]


def build_embedding_provider(
    name: str,
    checkpoint: str | None = None,
    pretrained: str | None = None,
    device: str | None = None,
) -> EmbeddingProviderPort:
    """Instantiate the selected provider. `checkpoint`/`pretrained`/`device`
    are ignored by the local embedder and default to each model's recommended
    checkpoint when empty."""
    checkpoint = checkpoint or None
    pretrained = pretrained or None
    device = device or None

    if name == "local":
        return LocalDeterministicEmbedder()
    if name == "siglip2":
        return SigLIP2Embedder(checkpoint=checkpoint, device=device)
    if name == "openclip":
        return OpenClipEmbedder(checkpoint=checkpoint, pretrained=pretrained, device=device)
    if name == "dinov2":
        return DinoV2Embedder(checkpoint=checkpoint, device=device)
    raise ValueError(
        f"unknown embedding provider '{name}'; known: ['local', 'siglip2', 'openclip', 'dinov2']"
    )
