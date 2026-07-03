"""Default reranker: cosine similarity, optionally blended with a
compositional modifier vector.

score = cos(query, candidate)                              (plain rerank)
score = (1-w)*cos(query, cand) + w*cos(modifier, cand)     (compositional)

This is the pluggable rerank stage (NFR17); a cross-encoder or MLLM reranker
implements the same RerankerPort. The blend is what makes a composed query
("like this, but in blue") pull candidates toward the modifier while staying
anchored to the reference image.
"""

from __future__ import annotations

import numpy as np

from ai_service.application.ports_rerank import RerankerPort

RERANKER_VERSION = "local-cosine-rerank-v1"


class CosineBlendReranker(RerankerPort):
    @property
    def model_version(self) -> str:
        return RERANKER_VERSION

    def score(
        self,
        query_vector: list[float],
        candidates: list[tuple[str, list[float]]],
        modifier_vector: list[float] | None,
        modifier_weight: float,
    ) -> list[tuple[str, float]]:
        query = _unit(np.asarray(query_vector, dtype=np.float64))
        modifier = (
            _unit(np.asarray(modifier_vector, dtype=np.float64))
            if modifier_vector is not None
            else None
        )
        weight = min(max(modifier_weight, 0.0), 1.0) if modifier is not None else 0.0

        out: list[tuple[str, float]] = []
        for cid, vec in candidates:
            cand = _unit(np.asarray(vec, dtype=np.float64))
            score = float(query @ cand)
            if modifier is not None:
                score = (1.0 - weight) * score + weight * float(modifier @ cand)
            out.append((cid, score))
        return out


def _unit(vector: np.ndarray) -> np.ndarray:
    norm = np.linalg.norm(vector)
    return vector if norm == 0.0 else vector / norm
