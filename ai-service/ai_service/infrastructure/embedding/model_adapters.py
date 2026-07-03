"""Real-model encoder adapters — the swap-in path (NFR16).

These are deliberate, honest stubs. Loading SigLIP 2 or DINOv2 requires
torch, GPU-class hardware, and multi-gigabyte weight downloads that the
local-first environment and credential-free CI cannot provide. Rather than
pretend, each adapter documents exactly what a real implementation does and
raises a clear error if selected without that work being done — so the seam
is real and visible, and enabling a model is a self-contained change to this
one file plus its dependencies.
"""

from __future__ import annotations

from ai_service.application.ports import EmbeddingProviderPort


class _UnavailableModelEmbedder(EmbeddingProviderPort):
    _name = "model"
    _dim = 0

    def __init__(self) -> None:
        raise NotImplementedError(
            f"the {self._name} encoder is not provisioned in this environment. "
            "A real implementation loads the model weights (torch + transformers) "
            "onto a GPU and implements embed_images/embed_texts against them. "
            "Use EMBEDDING_PROVIDER=local for the CPU default, or wire the weights "
            "here. See ai-service/README.md."
        )

    @property
    def model_version(self) -> str:  # pragma: no cover - unreachable until provisioned
        return self._name

    @property
    def embedding_dim(self) -> int:  # pragma: no cover
        return self._dim

    def embed_images(self, images):  # pragma: no cover
        raise NotImplementedError

    def embed_texts(self, texts):  # pragma: no cover
        raise NotImplementedError

    def perceptual_hash(self, image):  # pragma: no cover
        raise NotImplementedError


class SigLIP2Embedder(_UnavailableModelEmbedder):
    """SigLIP 2 — the architecture's primary semantic + multilingual +
    shared image/text encoder. Would produce genuine text-to-image
    alignment."""

    _name = "siglip2"
    _dim = 1152


class DinoV2Embedder(_UnavailableModelEmbedder):
    """DINOv2 — the architecture's secondary structural/fine-grained encoder
    (image-only)."""

    _name = "dinov2"
    _dim = 768
