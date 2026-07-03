"""The pluggable-encoder seam (NFR16).

An EmbeddingProviderPort turns images/text into vectors in one shared space
and computes perceptual hashes for dedup. Concrete providers live in
infrastructure/embedding; the composition root selects one by config. Nothing
above this port knows whether the vectors come from the local embedder,
SigLIP 2, or a future model.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class EmbeddingProviderPort(ABC):
    @property
    @abstractmethod
    def model_version(self) -> str: ...

    @property
    @abstractmethod
    def embedding_dim(self) -> int: ...

    @abstractmethod
    def embed_images(self, images: list[bytes]) -> list[list[float]]:
        """Batch-embed raw image bytes. Batching is the ingestion throughput
        lever (the architecture's 10-30x batched-vs-per-image goal)."""

    @abstractmethod
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Batch-embed text into the SAME space as embed_images, so a text
        query can be matched against image vectors (text-to-image search)."""

    @abstractmethod
    def perceptual_hash(self, image: bytes) -> str:
        """A perceptual hash (hex) for near-duplicate detection (FR1.2).
        Perceptually similar images hash to a small Hamming distance apart."""
