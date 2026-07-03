"""Core embedding concepts, independent of any model or framework."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Modality(str, Enum):
    IMAGE = "image"
    TEXT = "text"


@dataclass(frozen=True)
class Embedding:
    """A vector plus the provenance needed to reason about it later.

    `model_version` travels with every embedding so that when the encoder is
    swapped (SigLIP 2 → a successor, or the local default → a real model),
    stale vectors are identifiable and re-indexable (the architecture's
    model-version-tag requirement).
    """

    vector: tuple[float, ...]
    model_version: str

    @property
    def dim(self) -> int:
        return len(self.vector)
