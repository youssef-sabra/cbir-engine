"""Controllers for the public search API.

- image-to-image and composed queries take a multipart image upload (the
  natural "search by photo" shape);
- text-to-image takes a JSON body.

Metadata filters (hybrid search) are accepted as a JSON object. All endpoints
require the `search:query` scope via the gateway-role auth dependency.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from contextlib import AbstractContextManager

from cbir_common.auth import TenantContext
from fastapi import APIRouter, Depends, FastAPI, File, Form, Request, UploadFile
from pydantic import BaseModel, Field

from query_service.application.errors import EmbeddingServiceError, InvalidQueryError
from query_service.application.use_cases.bundle import UseCaseBundle
from query_service.domain.value_objects import SearchParameters
from query_service.interface_adapters import presenters

UnitOfWorkFactory = Callable[[], AbstractContextManager[UseCaseBundle]]
AuthDependency = Callable[..., TenantContext]

_MAX_UPLOAD_BYTES = 20 * 1024 * 1024  # 20 MB guardrail on query images


def _parse_filters(raw: str | None) -> dict:
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise InvalidQueryError("filters must be a JSON object") from exc
    if not isinstance(parsed, dict):
        raise InvalidQueryError("filters must be a JSON object")
    return parsed


def _params(top_k: int, offset: int, min_score: float, filters: dict) -> SearchParameters:
    # SearchParameters.__post_init__ enforces bounds and raises ValueError,
    # translated to 422 below.
    return SearchParameters(top_k=top_k, offset=offset, min_score=min_score, filters=filters)


async def _read_upload(file: UploadFile) -> bytes:
    data = await file.read()
    if not data:
        raise InvalidQueryError("uploaded image is empty")
    if len(data) > _MAX_UPLOAD_BYTES:
        raise InvalidQueryError("uploaded image exceeds the size limit")
    return data


class TextSearchRequest(BaseModel):
    query: str = Field(min_length=1)
    top_k: int = 10
    offset: int = 0
    min_score: float = 0.0
    filters: dict = Field(default_factory=dict)
    rerank: bool = False


def build_search_router(uow: UnitOfWorkFactory, require_query: AuthDependency) -> APIRouter:
    router = APIRouter(prefix="/v1/search", tags=["search"])

    @router.post("/image", response_model=presenters.SearchResponse)
    async def search_by_image(
        file: UploadFile = File(...),
        top_k: int = Form(10),
        offset: int = Form(0),
        min_score: float = Form(0.0),
        filters: str | None = Form(None),
        rerank: bool = Form(False),
        context: TenantContext = Depends(require_query),
    ):
        image_bytes = await _read_upload(file)
        params = _params(top_k, offset, min_score, _parse_filters(filters))
        with uow() as use_cases:
            output = use_cases.search.by_image(
                context.tenant_id, image_bytes, params, rerank=rerank
            )
        return presenters.present_results(output)

    @router.post("/text", response_model=presenters.SearchResponse)
    def search_by_text(body: TextSearchRequest, context: TenantContext = Depends(require_query)):
        params = _params(body.top_k, body.offset, body.min_score, body.filters)
        with uow() as use_cases:
            output = use_cases.search.by_text(
                context.tenant_id, body.query, params, rerank=body.rerank
            )
        return presenters.present_results(output)

    @router.post("/composed", response_model=presenters.SearchResponse)
    async def search_composed(
        file: UploadFile = File(...),
        modifier: str = Form(..., min_length=1),
        top_k: int = Form(10),
        offset: int = Form(0),
        min_score: float = Form(0.0),
        filters: str | None = Form(None),
        context: TenantContext = Depends(require_query),
    ):
        image_bytes = await _read_upload(file)
        params = _params(top_k, offset, min_score, _parse_filters(filters))
        with uow() as use_cases:
            output = use_cases.search.composed(context.tenant_id, image_bytes, modifier, params)
        return presenters.present_results(output)

    return router


def register_error_handlers(app: FastAPI) -> None:
    from fastapi.responses import JSONResponse

    @app.exception_handler(InvalidQueryError)
    def _invalid(request: Request, exc: InvalidQueryError):
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.exception_handler(ValueError)
    def _value(request: Request, exc: ValueError):
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.exception_handler(EmbeddingServiceError)
    def _embed_down(request: Request, exc: EmbeddingServiceError):
        # Recall stage unavailable — the query cannot be served; 503 signals
        # "retry later" rather than a client error.
        return JSONResponse(status_code=503, content={"detail": str(exc)})
