from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from ai_service.application.dto import EmbedBatchOutput, RerankOutput


class EmbeddingResultResponse(BaseModel):
    vector: list[float]
    phash: str | None


class EmbedResponse(BaseModel):
    # "model_version" is a real field name here, not a pydantic model_ config.
    model_config = ConfigDict(protected_namespaces=())

    model_version: str
    embedding_dim: int
    results: list[EmbeddingResultResponse]


class RerankItemResponse(BaseModel):
    id: str
    score: float


class RerankResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    model_version: str
    items: list[RerankItemResponse]


def present_embeddings(dto: EmbedBatchOutput) -> EmbedResponse:
    return EmbedResponse(
        model_version=dto.model_version,
        embedding_dim=dto.embedding_dim,
        results=[EmbeddingResultResponse(vector=r.vector, phash=r.phash) for r in dto.results],
    )


def present_rerank(dto: RerankOutput) -> RerankResponse:
    return RerankResponse(
        model_version=dto.model_version,
        items=[RerankItemResponse(id=i.id, score=i.score) for i in dto.items],
    )
