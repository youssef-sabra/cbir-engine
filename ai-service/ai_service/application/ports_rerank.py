"""The pluggable-reranker seam (NFR17)."""

from __future__ import annotations

from abc import ABC, abstractmethod


class RerankerPort(ABC):
    @property
    @abstractmethod
    def model_version(self) -> str: ...

    @abstractmethod
    def score(
        self,
        query_vector: list[float],
        candidates: list[tuple[str, list[float]]],
        modifier_vector: list[float] | None,
        modifier_weight: float,
    ) -> list[tuple[str, float]]:
        """Return (candidate_id, score) pairs, unsorted. Higher is better."""
