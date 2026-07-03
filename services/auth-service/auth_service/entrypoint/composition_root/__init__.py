"""Composition root: the single place where concrete infrastructure is wired
into use cases and the FastAPI application is assembled.

`build_app` accepts an optional `unit_of_work_factory` so tests can inject a
factory backed by in-memory fakes — the wiring below is what runs for real.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from contextlib import AbstractContextManager, contextmanager

import redis
from cbir_common.http import add_security_headers
from cbir_common.observability import instrument
from cbir_common.structured_logging import configure_logging
from fastapi import FastAPI, Response, status
from sqlalchemy import text

from auth_service.application.ports import SystemClock
from auth_service.application.use_cases.api_keys import (
    IssueApiKey,
    ListApiKeys,
    RevokeApiKey,
    RotateApiKey,
)
from auth_service.application.use_cases.bundle import UseCaseBundle
from auth_service.application.use_cases.credentials import (
    ValidateAccessTokenCredential,
    ValidateApiKeyCredential,
)
from auth_service.application.use_cases.tenants import CreateTenant, GetTenant, ListTenants
from auth_service.application.use_cases.tokens import IssueAccessToken
from auth_service.infrastructure.config import Settings
from auth_service.infrastructure.persistence import build_session_factory
from auth_service.infrastructure.ratelimit import RedisRateLimiter, RedisRevocationList
from auth_service.infrastructure.security import JwtTokenSigner, JwtTokenVerifier
from auth_service.interface_adapters.controllers import (
    build_admin_guard,
    build_admin_router,
    build_auth_router,
    register_error_handlers,
)
from auth_service.interface_adapters.gateways import (
    SqlAlchemyApiKeyRepository,
    SqlAlchemyTenantRepository,
)

logger = logging.getLogger(__name__)

UnitOfWorkFactory = Callable[[], AbstractContextManager[UseCaseBundle]]

# The dev defaults shipped in Settings — never acceptable in production.
_DEV_JWT_SECRET = "local-dev-jwt-secret-not-for-production"
_DEV_ADMIN_TOKEN = "local-dev-admin-token"


def _warn_on_dev_secrets(settings) -> None:
    if settings.auth_jwt_secret == _DEV_JWT_SECRET:
        logger.warning(
            "AUTH_JWT_SECRET is the built-in development default; set a strong secret "
            "from a secret manager before production."
        )
    if settings.auth_admin_token == _DEV_ADMIN_TOKEN:
        logger.warning(
            "AUTH_ADMIN_TOKEN is the built-in development default; set a strong token "
            "before production."
        )


def build_sql_unit_of_work_factory(settings: Settings) -> UnitOfWorkFactory:
    session_factory = build_session_factory(settings.database_url)
    redis_client = redis.Redis.from_url(settings.redis_url)
    rate_limiter = RedisRateLimiter(redis_client)
    revocation_list = RedisRevocationList(
        redis_client, token_ttl_seconds=settings.auth_access_token_ttl_seconds
    )
    signer = JwtTokenSigner(settings.auth_jwt_secret)
    verifier = JwtTokenVerifier(settings.auth_jwt_secret)
    clock = SystemClock()

    @contextmanager
    def unit_of_work():
        session = session_factory()
        try:
            tenants = SqlAlchemyTenantRepository(session)
            keys = SqlAlchemyApiKeyRepository(session)
            validate_api_key = ValidateApiKeyCredential(tenants, keys, rate_limiter, clock)
            yield UseCaseBundle(
                create_tenant=CreateTenant(tenants, clock),
                get_tenant=GetTenant(tenants),
                list_tenants=ListTenants(tenants),
                issue_api_key=IssueApiKey(tenants, keys, clock),
                list_api_keys=ListApiKeys(keys),
                rotate_api_key=RotateApiKey(
                    keys, clock, grace_seconds=settings.auth_api_key_grace_seconds
                ),
                revoke_api_key=RevokeApiKey(keys, revocation_list, clock),
                validate_api_key=validate_api_key,
                validate_access_token=ValidateAccessTokenCredential(
                    verifier, revocation_list, rate_limiter
                ),
                issue_access_token=IssueAccessToken(
                    validate_api_key, signer, ttl_seconds=settings.auth_access_token_ttl_seconds
                ),
            )
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    return unit_of_work


def build_app(
    settings: Settings | None = None,
    unit_of_work_factory: UnitOfWorkFactory | None = None,
) -> FastAPI:
    settings = settings or Settings()
    configure_logging(settings.service_name)
    _warn_on_dev_secrets(settings)
    uow = unit_of_work_factory or build_sql_unit_of_work_factory(settings)

    app = FastAPI(
        title=settings.service_name,
        version=settings.service_version,
        description="Tenant identity, API key lifecycle, token issuance, rate limiting.",
    )
    instrument(app, settings.service_name)
    add_security_headers(app)
    register_error_handlers(app)
    app.include_router(build_admin_router(uow, build_admin_guard(settings.auth_admin_token)))
    app.include_router(build_auth_router(uow))

    @app.get("/health", tags=["ops"])
    def health() -> dict:
        return {
            "status": "ok",
            "service": settings.service_name,
            "version": settings.service_version,
        }

    # Built once, lazily connecting — engines don't open connections until used,
    # so this is safe even when tests inject an in-memory unit of work.
    readiness_session_factory = build_session_factory(settings.database_url)

    @app.get("/readyz", tags=["ops"])
    def readyz(response: Response) -> dict:
        results = {}
        try:
            with readiness_session_factory() as session:
                session.execute(text("SELECT 1"))
            results["postgres"] = {"reachable": True}
        except Exception:
            results["postgres"] = {"reachable": False}
        try:
            redis.Redis.from_url(settings.redis_url, socket_connect_timeout=2).ping()
            results["redis"] = {"reachable": True}
        except Exception:
            results["redis"] = {"reachable": False}
        all_ok = all(r["reachable"] for r in results.values())
        if not all_ok:
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {
            "status": "ok" if all_ok else "degraded",
            "service": settings.service_name,
            "dependencies": results,
        }

    return app
