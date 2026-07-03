from __future__ import annotations

from dataclasses import dataclass

from ai_service.domain.value_objects import Modality


@dataclass(frozen=True)
class EmbedInput:
    modality: Modality
    # exactly one of these is set, matching the modality
    image_bytes: bytes | None = None
    text: str | None = None


@dataclass(frozen=True)
class EmbeddingResult:
    vector: list[float]
    phash: str | None  # only for images, and only when requested


@dataclass(frozen=True)
class EmbedBatchOutput:
    model_version: str
    embedding_dim: int
    results: list[EmbeddingResult]


@dataclass(frozen=True)
class RerankCandidate:
    id: str
    vector: list[float]


@dataclass(frozen=True)
class RerankInput:
    query_vector: list[float]
    candidates: list[RerankCandidate]
    # optional compositional modifier: a second vector (e.g. text "in blue")
    # blended into the score to steer results (Milestone 9).
    modifier_vector: list[float] | None = None
    modifier_weight: float = 0.5
    top_k: int | None = None


@dataclass(frozen=True)
class RerankedItem:
    id: str
    score: float


@dataclass(frozen=True)
class RerankOutput:
    model_version: str
    items: list[RerankedItem]
