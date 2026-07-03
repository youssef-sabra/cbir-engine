"""Deterministic, CPU-only embedder — the local-first default.

It produces genuinely useful *image-to-image* similarity (perceptually
similar images land near each other) from cheap, dependency-light features:

  - a 16x16 grayscale thumbnail (256 dims) captures coarse structure/layout;
  - an 8x8 RGB thumbnail (192 dims) captures color layout;
  - a 64-bin luminance histogram (64 dims) captures overall tone.

Total 512 dims, L2-normalized so cosine similarity is meaningful. This is not
a learned semantic model — text embeddings share the vector space
dimensionally but NOT semantically (a hashed bag-of-tokens), so text-to-image
results are structurally correct but not semantically aligned. Real
cross-modal semantics arrive by swapping in the SigLIP 2 adapter (NFR16).

Deterministic by construction: the same bytes always yield the same vector,
which makes ingestion reproducible and the query-embedding cache correct.
"""

from __future__ import annotations

import hashlib

import numpy as np
from PIL import Image

from ai_service.application.errors import InvalidImageError
from ai_service.application.ports import EmbeddingProviderPort
from ai_service.infrastructure.embedding.phash import InvalidImageBytes, average_hash, open_image

LOCAL_EMBEDDING_DIM = 512
MODEL_VERSION = "local-hash-v1"
_GRAY_SIDE = 16  # 256 dims
_RGB_SIDE = 8  # 192 dims
_HIST_BINS = 64  # 64 dims


class LocalDeterministicEmbedder(EmbeddingProviderPort):
    @property
    def model_version(self) -> str:
        return MODEL_VERSION

    @property
    def embedding_dim(self) -> int:
        return LOCAL_EMBEDDING_DIM

    def embed_images(self, images: list[bytes]) -> list[list[float]]:
        return [self._embed_image(b) for b in images]

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_text(t) for t in texts]

    def perceptual_hash(self, image: bytes) -> str:
        try:
            return average_hash(image)
        except InvalidImageBytes as exc:
            raise InvalidImageError(str(exc)) from exc

    # -- internals ------------------------------------------------------------

    def _open(self, image: bytes) -> Image.Image:
        try:
            return open_image(image)
        except InvalidImageBytes as exc:
            raise InvalidImageError(str(exc)) from exc

    def _embed_image(self, image: bytes) -> list[float]:
        img = self._open(image).convert("RGB")
        gray = np.asarray(
            img.convert("L").resize((_GRAY_SIDE, _GRAY_SIDE), Image.BILINEAR), dtype=np.float64
        ).flatten()
        rgb = np.asarray(
            img.resize((_RGB_SIDE, _RGB_SIDE), Image.BILINEAR), dtype=np.float64
        ).flatten()
        hist, _ = np.histogram(gray, bins=_HIST_BINS, range=(0.0, 255.0))
        vector = np.concatenate([gray, rgb, hist.astype(np.float64)])
        return _l2_normalize(vector).tolist()

    def _embed_text(self, text: str) -> list[float]:
        vector = np.zeros(LOCAL_EMBEDDING_DIM, dtype=np.float64)
        tokens = [t for t in text.lower().split() if t]
        for token in tokens:
            # Two hashed positions per token spreads mass and reduces collisions.
            digest = hashlib.sha1(token.encode("utf-8")).digest()
            idx1 = int.from_bytes(digest[0:4], "big") % LOCAL_EMBEDDING_DIM
            idx2 = int.from_bytes(digest[4:8], "big") % LOCAL_EMBEDDING_DIM
            vector[idx1] += 1.0
            vector[idx2] += 1.0
        return _l2_normalize(vector).tolist()


def _l2_normalize(vector: np.ndarray) -> np.ndarray:
    norm = np.linalg.norm(vector)
    if norm == 0.0:
        # An all-zero input (e.g. empty text) maps to a fixed unit vector so
        # downstream cosine math never divides by zero.
        out = np.zeros_like(vector)
        out[0] = 1.0
        return out
    return vector / norm
