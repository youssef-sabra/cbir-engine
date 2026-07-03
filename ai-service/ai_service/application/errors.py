"""Application errors, translated to HTTP by the controllers layer."""

from __future__ import annotations


class InvalidImageError(Exception):
    """Bytes could not be decoded as an image the encoder understands."""


class EmptyBatchError(Exception):
    """An embed/rerank request arrived with nothing to process."""
