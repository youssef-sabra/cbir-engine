"""Tests for the real encoder adapters.

These are gated twice: they skip unless (a) torch is importable AND (b) the
env var CBIR_RUN_ML_TESTS is set. That keeps them out of the default `pytest`
run and CI (no torch, no multi-GB weight download) while making them runnable
on demand:

    pip install -r requirements.txt -r requirements-ml.txt
    CBIR_RUN_ML_TESTS=1 python -m pytest tests/test_model_adapters.py -v

The provider factory (which does NOT import torch) is always tested.
"""

from __future__ import annotations

import io
import os

import pytest

from ai_service.infrastructure.embedding import build_embedding_provider


def _png(color, size=64) -> bytes:
    from PIL import Image

    b = io.BytesIO()
    Image.new("RGB", (size, size), color).save(b, format="PNG")
    return b.getvalue()


def _cos(a, b) -> float:
    import numpy as np

    return float(np.asarray(a) @ np.asarray(b))


# --- always-on: factory routing (no torch) -----------------------------------


class TestFactory:
    def test_local_provider_builds_without_ml_deps(self):
        provider = build_embedding_provider("local")
        assert provider.embedding_dim == 512

    def test_unknown_provider_raises(self):
        with pytest.raises(ValueError, match="unknown embedding provider"):
            build_embedding_provider("nope")
        # The error must name the real providers so operators know the options.
        try:
            build_embedding_provider("nope")
        except ValueError as exc:
            for name in ("local", "siglip2", "openclip", "dinov2"):
                assert name in str(exc)


# --- gated: real model behaviour ---------------------------------------------

_run_ml = bool(os.environ.get("CBIR_RUN_ML_TESTS"))
pytestmark = pytest.mark.skipif(
    not _run_ml, reason="set CBIR_RUN_ML_TESTS=1 (and install requirements-ml.txt) to run"
)


@pytest.fixture(scope="module")
def siglip():
    pytest.importorskip("torch")
    pytest.importorskip("transformers")
    return build_embedding_provider("siglip2")


class TestSigLIP2:
    def test_image_embeddings_normalized_and_shared_dim(self, siglip):
        import numpy as np

        vecs = siglip.embed_images([_png((220, 30, 30)), _png((30, 30, 220))])
        assert all(len(v) == siglip.embedding_dim for v in vecs)
        assert all(abs(np.linalg.norm(v) - 1.0) < 1e-3 for v in vecs)

    def test_similar_images_closer_than_dissimilar(self, siglip):
        red, red2, blue = siglip.embed_images(
            [_png((220, 30, 30)), _png((205, 45, 45)), _png((30, 30, 220))]
        )
        assert _cos(red, red2) > _cos(red, blue)

    def test_text_shares_space_with_images(self, siglip):
        img = siglip.embed_images([_png((220, 30, 30))])[0]
        txt = siglip.embed_texts(["a solid red image"])[0]
        assert len(txt) == len(img)  # same shared space

    def test_perceptual_hash_still_works(self, siglip):
        h = siglip.perceptual_hash(_png((128, 128, 128)))
        assert len(h) == 16


class TestDinoV2ImageOnly:
    def test_text_embedding_is_rejected(self):
        pytest.importorskip("torch")
        from ai_service.application.errors import InvalidImageError

        provider = build_embedding_provider("dinov2")
        with pytest.raises(InvalidImageError, match="image-only"):
            provider.embed_texts(["x"])
