"""Core search concepts, framework-independent."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RankedResult:
    item_id: str
    score: float
    payload: dict


@dataclass(frozen=True)
class SearchParameters:
    """Validated query knobs. Constructing this enforces the invariants
    (positive top_k, score in range) so invalid searches are unrepresentable
    rather than checked ad hoc."""

    top_k: int
    offset: int
    min_score: float
    filters: dict

    MAX_TOP_K = 100

    def __post_init__(self) -> None:
        if not (1 <= self.top_k <= self.MAX_TOP_K):
            raise ValueError(f"top_k must be between 1 and {self.MAX_TOP_K}")
        if self.offset < 0:
            raise ValueError("offset must be non-negative")
        if not (0.0 <= self.min_score <= 1.0):
            raise ValueError("min_score must be between 0.0 and 1.0")
