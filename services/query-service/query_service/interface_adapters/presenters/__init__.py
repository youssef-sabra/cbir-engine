from __future__ import annotations

from pydantic import BaseModel

from query_service.application.dto import SearchResultsOutput


class RankedResultResponse(BaseModel):
    item_id: str
    score: float
    metadata: dict


class SearchResponse(BaseModel):
    results: list[RankedResultResponse]
    count: int
    cached: bool
    reranked: bool


def present_results(dto: SearchResultsOutput) -> SearchResponse:
    return SearchResponse(
        results=[
            RankedResultResponse(item_id=r.item_id, score=r.score, metadata=r.payload)
            for r in dto.results
        ],
        count=len(dto.results),
        cached=dto.cached,
        reranked=dto.reranked,
    )
