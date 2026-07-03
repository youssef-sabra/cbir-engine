"""Controllers: translate HTTP requests into use-case invocations.

Routers are built by factories taking a `UnitOfWorkFactory` — a callable
context manager yielding a fully-wired UseCaseBundle. The composition root
decides what's behind it (real PostgreSQL/Redis or in-memory fakes for
tests); controllers neither know nor care.
"""

from __future__ import annotations

import hmac
from collections.abc import Callable
from contextlib import AbstractContextManager

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

from auth_service.application.dto import CreateTenantInput, IssueApiKeyInput
from auth_service.application.errors import (
    ApiKeyNotFoundError,
    AuthenticationError,
    RateLimitExceededError,
    TenantNameConflictError,
    TenantNotFoundError,
)
from auth_service.application.use_cases.bundle import UseCaseBundle
from auth_service.domain.value_objects import UnknownScopeError
from auth_service.interface_adapters import presenters

UnitOfWorkFactory = Callable[[], AbstractContextManager[UseCaseBundle]]


# --- Request schemas (input shape belongs to the controller layer) -----------


class CreateTenantRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    plan_tier: str = "free"
    settings: dict = Field(default_factory=dict)


class IssueApiKeyRequest(BaseModel):
    name: str = Field(default="default", max_length=200)
    scopes: list[str] | None = None
    rate_limit_per_minute: int | None = Field(default=None, ge=1)
    expires_in_days: int | None = Field(default=None, ge=1)


class TokenRequest(BaseModel):
    api_key: str


# --- Admin guard --------------------------------------------------------------


def build_admin_guard(admin_token: str) -> Callable[[Request], None]:
    """Shared-secret guard for the manual-provisioning admin API.

    This is deliberately minimal internal tooling (Milestone 2 scope) —
    replaced by real operator identity once the self-serve dashboard and
    RBAC arrive (Milestone 11 / FR4.3).
    """

    def guard(request: Request) -> None:
        presented = request.headers.get("X-Admin-Token", "")
        if not presented or not hmac.compare_digest(presented, admin_token):
            raise HTTPException(status_code=401, detail="invalid or missing admin token")

    return guard


# --- Routers -------------------------------------------------------------------


def build_admin_router(uow: UnitOfWorkFactory, admin_guard) -> APIRouter:
    router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(admin_guard)])

    @router.post("/tenants", status_code=201, response_model=presenters.TenantResponse)
    def create_tenant(body: CreateTenantRequest):
        with uow() as use_cases:
            output = use_cases.create_tenant.execute(
                CreateTenantInput(name=body.name, plan_tier=body.plan_tier, settings=body.settings)
            )
        return presenters.present_tenant(output)

    @router.get("/tenants", response_model=list[presenters.TenantResponse])
    def list_tenants(limit: int = 50, offset: int = 0):
        with uow() as use_cases:
            outputs = use_cases.list_tenants.execute(limit=limit, offset=offset)
        return [presenters.present_tenant(o) for o in outputs]

    @router.get("/tenants/{tenant_id}", response_model=presenters.TenantResponse)
    def get_tenant(tenant_id: str):
        with uow() as use_cases:
            output = use_cases.get_tenant.execute(tenant_id)
        return presenters.present_tenant(output)

    @router.post(
        "/tenants/{tenant_id}/api-keys",
        status_code=201,
        response_model=presenters.IssuedApiKeyResponse,
    )
    def issue_api_key(tenant_id: str, body: IssueApiKeyRequest):
        with uow() as use_cases:
            output = use_cases.issue_api_key.execute(
                IssueApiKeyInput(
                    tenant_id=tenant_id,
                    name=body.name,
                    scopes=tuple(body.scopes) if body.scopes is not None else None,
                    rate_limit_per_minute=body.rate_limit_per_minute,
                    expires_in_days=body.expires_in_days,
                )
            )
        return presenters.present_issued_key(output)

    @router.get(
        "/tenants/{tenant_id}/api-keys",
        response_model=list[presenters.ApiKeyMetadataResponse],
    )
    def list_api_keys(tenant_id: str):
        with uow() as use_cases:
            outputs = use_cases.list_api_keys.execute(tenant_id)
        return [presenters.present_key_metadata(o) for o in outputs]

    @router.post(
        "/api-keys/{key_id}/rotate",
        status_code=201,
        response_model=presenters.IssuedApiKeyResponse,
    )
    def rotate_api_key(key_id: str):
        with uow() as use_cases:
            output = use_cases.rotate_api_key.execute(key_id)
        return presenters.present_issued_key(output)

    @router.post("/api-keys/{key_id}/revoke", response_model=presenters.ApiKeyMetadataResponse)
    def revoke_api_key(key_id: str):
        with uow() as use_cases:
            output = use_cases.revoke_api_key.execute(key_id)
        return presenters.present_key_metadata(output)

    return router


def build_auth_router(uow: UnitOfWorkFactory) -> APIRouter:
    router = APIRouter(tags=["auth"])

    @router.post("/v1/auth/token", response_model=presenters.AccessTokenResponse)
    def issue_token(body: TokenRequest):
        with uow() as use_cases:
            output = use_cases.issue_access_token.execute(body.api_key)
        return presenters.present_access_token(output)

    @router.post("/internal/validate", response_model=presenters.ValidatedContextResponse)
    def validate(request: Request):
        """The gateway-role endpoint: resource services forward credentials
        here and receive a TenantContext (200), 401, or 429."""
        api_key = request.headers.get("X-API-Key")
        authorization = request.headers.get("Authorization", "")
        with uow() as use_cases:
            if api_key:
                output = use_cases.validate_api_key.execute(api_key)
            elif authorization.lower().startswith("bearer "):
                output = use_cases.validate_access_token.execute(authorization[7:].strip())
            else:
                raise AuthenticationError(
                    "missing credentials: provide X-API-Key or Authorization: Bearer"
                )
        return presenters.present_auth_context(output)

    return router


# --- Error translation ---------------------------------------------------------


def register_error_handlers(app: FastAPI) -> None:
    from fastapi.responses import JSONResponse

    @app.exception_handler(AuthenticationError)
    def _authentication_error(request: Request, exc: AuthenticationError):
        return JSONResponse(
            status_code=401,
            content={"detail": str(exc)},
            headers={"WWW-Authenticate": "Bearer"},
        )

    @app.exception_handler(RateLimitExceededError)
    def _rate_limited(request: Request, exc: RateLimitExceededError):
        return JSONResponse(
            status_code=429,
            content={"detail": str(exc)},
            headers={"Retry-After": str(exc.retry_after_seconds)},
        )

    @app.exception_handler(TenantNotFoundError)
    @app.exception_handler(ApiKeyNotFoundError)
    def _not_found(request: Request, exc: Exception):
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(TenantNameConflictError)
    def _conflict(request: Request, exc: TenantNameConflictError):
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(UnknownScopeError)
    @app.exception_handler(ValueError)
    def _bad_request(request: Request, exc: Exception):
        return JSONResponse(status_code=422, content={"detail": str(exc)})
