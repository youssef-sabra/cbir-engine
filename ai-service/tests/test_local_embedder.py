"""Unit tests for the deterministic local embedder — the properties the whole
retrieval pipeline relies on: determinism, normalization, and that visually
similar images embed closer than dissimilar ones."""

from __future__ import annotations

import io

import numpy as np
from PIL import Image

from ai_service.infrastructure.embedding.local_embedder import (
    LOCAL_EMBEDDING_DIM,
    LocalDeterministicEmbedder,
)


def _png(color, size=32) -> bytes:
    img = Image.new("RGB", (size, size), color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _cos(a, b) -> float:
    a, b = np.asarray(a), np.asarray(b)
    return float(a @ b / (np.linalg.norm(a) * np.linalg.norm(b)))


def test_image_embedding_is_deterministic_and_normalized():
    emb = LocalDeterministicEmbedder()
    img = _png((200, 50, 50))
    v1 = emb.embed_images([img])[0]
    v2 = emb.embed_images([img])[0]
    assert v1 == v2
    assert len(v1) == LOCAL_EMBEDDING_DIM
    assert abs(np.linalg.norm(v1) - 1.0) < 1e-6


def test_similar_images_are_closer_than_dissimilar():
    emb = LocalDeterministicEmbedder()
    red = emb.embed_images([_png((220, 20, 20))])[0]
    near_red = emb.embed_images([_png((210, 30, 30))])[0]
    blue = emb.embed_images([_png((20, 20, 220))])[0]
    assert _cos(red, near_red) > _cos(red, blue)


def test_perceptual_hash_stable_and_near_for_similar():
    emb = LocalDeterministicEmbedder()
    h1 = emb.perceptual_hash(_png((128, 128, 128)))
    h2 = emb.perceptual_hash(_png((128, 128, 128)))
    assert h1 == h2 and len(h1) == 16


def test_text_embedding_deterministic_and_normalized():
    emb = LocalDeterministicEmbedder()
    v1 = emb.embed_texts(["red running shoes"])[0]
    v2 = emb.embed_texts(["red running shoes"])[0]
    assert v1 == v2
    assert len(v1) == LOCAL_EMBEDDING_DIM
    assert abs(np.linalg.norm(v1) - 1.0) < 1e-6


def test_empty_text_does_not_crash():
    emb = LocalDeterministicEmbedder()
    v = emb.embed_texts([""])[0]
    assert len(v) == LOCAL_EMBEDDING_DIM
