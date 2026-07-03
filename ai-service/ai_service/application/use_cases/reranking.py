"""Reranking use case (Milestone 9).

Re-scores a candidate shortlist against the query, optionally blending in a
compositional modifier vector ("like this, but in blue"). This is the
pluggable rerank stage the architecture calls for; the scoring itself is
delegated to a RerankerPort so a cross-encoder or MLLM reranker can replace
the default cosine-blend without touching this orchestration.
"""

from __future__ import annotations

from ai_service.application.dto import RerankedItem, RerankInput, RerankOutput
from ai_service.application.errors import EmptyBatchError
from ai_service.application.ports_rerank import RerankerPort


class RerankShortlist:
    def __init__(self, reranker: RerankerPort) -> None:
        self._reranker = reranker

    def execute(self, data: RerankInput) -> RerankOutput:
        if not data.candidates:
            raise EmptyBatchError("rerank request contained no candidates")
        scored = self._reranker.score(
            query_vector=data.query_vector,
            candidates=[(c.id, c.vector) for c in data.candidates],
            modifier_vector=data.modifier_vector,
            modifier_weight=data.modifier_weight,
        )
        scored.sort(key=lambda pair: pair[1], reverse=True)
        if data.top_k is not None:
            scored = scored[: data.top_k]
        return RerankOutput(
            model_version=self._reranker.model_version,
            items=[RerankedItem(id=cid, score=score) for cid, score in scored],
        )
