from __future__ import annotations

from dataclasses import dataclass

from query_service.domain.value_objects import RankedResult


@dataclass(frozen=True)
class SearchResultsOutput:
    results: list[RankedResult]
    cached: bool
    reranked: bool
