"""Controllers for the catalog API.

Authentication is a FastAPI dependency injected by the composition root —
built from cbir_common's gateway-style validator in production, replaced by
a stub in unit tests. Endpoints declare which scope they require; data
isolation comes from passing the validated context's tenant_id into every
use case (there is no code path that queries without it).
"""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager

from cbir_common.auth import TenantContext
from fastapi import APIRouter, Depends, FastAPI, Request
from pydantic import BaseModel, Field

from catalog_service.application.dto import (
    BatchRegisterInput,
    RegisterItemInput,
)
from catalog_service.application.errors import (
    DuplicateExternalIdError,
    ItemNotFoundError,
    ObjectStorageError,
    UnsupportedContentTypeError,
    UploadNotConfirmableError,
)
from catalog_service.application.use_cases.bundle import UseCaseBundle
from catalog_service.interface_adapters import presenters

UnitOfWorkFactory = Callable[[], AbstractContextManager[UseCaseBundle]]
AuthDependency = Callable[..., TenantContext]


class RegisterItemRequest(BaseModel):
    content_type: str
    metadata: dict = Field(default_factory=dict)
    external_id: str | None = Field(default=None, max_length=500)


class BatchRegisterRequest(BaseModel):
    # Batch upload / manifest import (FR1.1): one call registers many items,
    # each returned with its own signed upload URL.
    items: list[RegisterItemRequest] = Field(min_length=1, max_length=1000)


class FeedbackRequest(BaseModel):
    item_id: str
    query_ref: str = Field(min_length=1, max_length=500)
    relevant: bool


def build_items_router(
    uow: UnitOfWorkFactory,
    require_read: AuthDependency,
    require_write: AuthDependency,
) -> APIRouter:
    router = APIRouter(prefix="/v1/items", tags=["catalog"])

    @router.post("", status_code=201, response_model=presenters.RegisteredItemResponse)
    def register_item(body: RegisterItemRequest, context: TenantContext = Depends(require_write)):
        with uow() as use_cases:
            output = use_cases.register_item.execute(
                RegisterItemInput(
                    tenant_id=context.tenant_id,
                    content_type=body.content_type,
                    metadata=body.metadata,
                    external_id=body.external_id,
                )
            )
        return presenters.present_registered(output)

    @router.post("/batch", status_code=201, response_model=presenters.BatchRegisteredResponse)
    def batch_register(body: BatchRegisterRequest, context: TenantContext = Depends(require_write)):
        with uow() as use_cases:
            output = use_cases.batch_register.execute(
                BatchRegisterInput(
                    tenant_id=context.tenant_id,
                    items=[
                        RegisterItemInput(
                            tenant_id=context.tenant_id,
                            content_type=i.content_type,
                            metadata=i.metadata,
                            external_id=i.external_id,
                        )
                        for i in body.items
                    ],
                )
            )
        return presenters.present_batch(output)

    @router.post("/{item_id}/confirm", response_model=presenters.ItemResponse)
    def confirm_upload(item_id: str, context: TenantContext = Depends(require_write)):
        with uow() as use_cases:
            output = use_cases.confirm_upload.execute(context.tenant_id, item_id)
        return presenters.present_item(output)

    @router.get("", response_model=list[presenters.ItemResponse])
    def list_items(
        limit: int = 50,
        offset: int = 0,
        status: str | None = None,
        context: TenantContext = Depends(require_read),
    ):
        with uow() as use_cases:
            outputs = use_cases.list_items.execute(context.tenant_id, limit, offset, status=status)
        return [presenters.present_item(o) for o in outputs]

    @router.get("/{item_id}", response_model=presenters.ItemWithDownloadResponse)
    def get_item(item_id: str, context: TenantContext = Depends(require_read)):
        with uow() as use_cases:
            output = use_cases.get_item.execute(context.tenant_id, item_id)
        return presenters.present_item_with_download(output)

    @router.delete("/{item_id}", status_code=204)
    def delete_item(item_id: str, context: TenantContext = Depends(require_write)):
        with uow() as use_cases:
            use_cases.delete_item.execute(context.tenant_id, item_id)

    return router


def build_feedback_router(uow: UnitOfWorkFactory, require_write: AuthDependency) -> APIRouter:
    router = APIRouter(prefix="/v1/feedback", tags=["feedback"])

    @router.post("", status_code=201)
    def submit_feedback(body: FeedbackRequest, context: TenantContext = Depends(require_write)):
        with uow() as use_cases:
            feedback_id = use_cases.submit_feedback.execute(
                context.tenant_id, body.item_id, body.query_ref, body.relevant
            )
        return {"id": feedback_id, "status": "recorded"}

    return router


def register_error_handlers(app: FastAPI) -> None:
    from fastapi.responses import JSONResponse

    @app.exception_handler(ItemNotFoundError)
    def _not_found(request: Request, exc: ItemNotFoundError):
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(DuplicateExternalIdError)
    @app.exception_handler(UploadNotConfirmableError)
    def _conflict(request: Request, exc: Exception):
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(UnsupportedContentTypeError)
    def _unsupported(request: Request, exc: UnsupportedContentTypeError):
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.exception_handler(ValueError)
    def _bad_value(request: Request, exc: ValueError):
        # e.g. an unknown ?status= filter value reaching ItemStatus(...).
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.exception_handler(ObjectStorageError)
    def _storage_error(request: Request, exc: ObjectStorageError):
        return JSONResponse(status_code=502, content={"detail": str(exc)})
