"""HTTP controllers for the ai-service internal API.

These endpoints are internal (called by the ingestion worker and
query-service over the Compose network), not public — there is no tenant
auth here; network isolation is the boundary, exactly like a model-serving
sidecar. Images cross the wire base64-encoded in JSON.
"""

from __future__ import annotations

import base64

from fastapi import APIRouter, FastAPI, Request
from pydantic import BaseModel, Field

from ai_service.application.dto import EmbedInput, RerankCandidate, RerankInput
from ai_service.application.errors import EmptyBatchError, InvalidImageError
from ai_service.application.use_cases.bundle import UseCaseBundle
from ai_service.domain.value_objects import Modality
from ai_service.interface_adapters import presenters


class EmbedItemRequest(BaseModel):
    modality: Modality
    image_base64: str | None = None
    text: str | None = None


class EmbedRequest(BaseModel):
    inputs: list[EmbedItemRequest] = Field(min_length=1)
    include_phash: bool = False


class RerankCandidateRequest(BaseModel):
    id: str
    vector: list[float]


class RerankRequest(BaseModel):
    query_vector: list[float]
    candidates: list[RerankCandidateRequest] = Field(min_length=1)
    modifier_vector: list[float] | None = None
    modifier_weight: float = 0.5
    top_k: int | None = Field(default=None, ge=1)


def _to_embed_input(item: EmbedItemRequest) -> EmbedInput:
    if item.modality is Modality.IMAGE:
        if not item.image_base64:
            raise InvalidImageError("image modality requires image_base64")
        try:
            raw = base64.b64decode(item.image_base64, validate=True)
        except (ValueError, TypeError) as exc:
            raise InvalidImageError("image_base64 is not valid base64") from exc
        return EmbedInput(modality=Modality.IMAGE, image_bytes=raw)
    return EmbedInput(modality=Modality.TEXT, text=item.text or "")


def build_internal_router(use_cases: UseCaseBundle) -> APIRouter:
    router = APIRouter(prefix="/internal", tags=["ai"])

    @router.post("/embed", response_model=presenters.EmbedResponse)
    def embed(body: EmbedRequest):
        inputs = [_to_embed_input(i) for i in body.inputs]
        output = use_cases.generate_embeddings.execute(inputs, include_phash=body.include_phash)
        return presenters.present_embeddings(output)

    @router.post("/rerank", response_model=presenters.RerankResponse)
    def rerank(body: RerankRequest):
        output = use_cases.rerank_shortlist.execute(
            RerankInput(
                query_vector=body.query_vector,
                candidates=[RerankCandidate(id=c.id, vector=c.vector) for c in body.candidates],
                modifier_vector=body.modifier_vector,
                modifier_weight=body.modifier_weight,
                top_k=body.top_k,
            )
        )
        return presenters.present_rerank(output)

    return router


def register_error_handlers(app: FastAPI) -> None:
    from fastapi.responses import JSONResponse

    @app.exception_handler(InvalidImageError)
    def _invalid_image(request: Request, exc: InvalidImageError):
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.exception_handler(EmptyBatchError)
    def _empty(request: Request, exc: EmptyBatchError):
        return JSONResponse(status_code=422, content={"detail": str(exc)})
