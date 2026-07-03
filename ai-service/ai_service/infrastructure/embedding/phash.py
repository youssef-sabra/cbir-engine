"""Perceptual hashing for near-duplicate detection (FR1.2).

Deliberately separate from the semantic encoder: dedup asks "are these the
same picture?", which is a cheap, model-independent pixel question, whereas
the encoder asks "what does this picture mean?". Every provider — the local
embedder, SigLIP 2, OpenCLIP — reuses this same average-hash so dedup
behaviour is identical regardless of which semantic model is active.
"""

from __future__ import annotations

import io

import numpy as np
from PIL import Image, UnidentifiedImageError


class InvalidImageBytes(Exception):
    """Bytes could not be decoded as an image."""


def open_image(image: bytes) -> Image.Image:
    try:
        return Image.open(io.BytesIO(image))
    except (UnidentifiedImageError, OSError) as exc:
        raise InvalidImageBytes("could not decode image bytes") from exc


def average_hash(image: bytes, hash_side: int = 8) -> str:
    """aHash: downscale to hash_side x hash_side grayscale, threshold at the
    mean, pack the bits into a hex string. Perceptually similar images differ
    in only a few bits (small Hamming distance)."""
    img = open_image(image).convert("L").resize((hash_side, hash_side), Image.BILINEAR)
    pixels = np.asarray(img, dtype=np.float64)
    bits = (pixels > pixels.mean()).flatten()
    value = 0
    for bit in bits:
        value = (value << 1) | int(bit)
    width = (hash_side * hash_side) // 4
    return f"{value:0{width}x}"
