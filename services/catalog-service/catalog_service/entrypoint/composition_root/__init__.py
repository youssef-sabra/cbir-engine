"""Composition root for catalog-service.

Tests inject `unit_of_work_factory` (in-memory repos + fake storage) and
`require_read`/`require_write` (stub auth); production wiring below uses
PostgreSQL, the S3 adapter, and gateway-style validation via auth-service.
"""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager, asynccontextmanager, contextmanager
from typing import Any

from cbir_common.auth import AuthServiceClient, build_scope_dependency
from cbir_common.structured_logging import configure_logging
from fastapi import FastAPI, Response, status
from sqlalchemy import text

from catalog_service.application.ports import SystemClock
from catalog_service.application.use_cases.bundle import UseCaseBundle
from catalog_service.application.use_cases.items import (
    ConfirmCatalogItemUpload,
    DeleteCatalogItem,
    GetCatalogItem,
    ListCatalogItems,
    RegisterCatalogItem,
)
from catalog_service.infrastructure.config import Settings
from catalog_service.infrastructure.object_storage import S3ObjectStorage
from catalog_service.infrastructure.persistence import build_session_factory
from catalog_service.interface_adapters.controllers import (
    build_items_router,
    register_error_handlers,
)
from catalog_service.interface_adapters.gateways import SqlAlchemyCatalogItemRepository

UnitOfWorkFactory = Callable[[], AbstractContextManager[UseCaseBundle]]


def build_app(
    settings: Settings | None = None,
    unit_of_work_factory: UnitOfWorkFactory | None = None,
    require_read: Callable[..., Any] | None = None,
    require_write: Callable[..., Any] | None = None,
) -> FastAPI:
    settings = settings or Settings()
    configure_logging(settings.service_name)

    storage: S3ObjectStorage | None = None
    auth_client: AuthServiceClient | None = None

    if unit_of_work_factory is None:
        session_factory = build_session_factory(settings.database_url)
        storage = S3ObjectStorage(
            endpoint_url=settings.s3_endpoint_url,
            presign_endpoint_url=settings.presign_endpoint,
            access_key=settings.s3_access_key,
            secret_key=settings.s3_secret_key,
            bucket=settings.s3_bucket_name,
            region=settings.s3_region,
        )
        clock = SystemClock()

        @contextmanager
        def sql_unit_of_work():
            session = session_factory()
            try:
                items = SqlAlchemyCatalogItemRepository(session)
                yield UseCaseBundle(
                    register_item=RegisterCatalogItem(
                        items,
                        storage,
                        clock,
                        allowed_content_types=settings.allowed_content_types,
                        upload_url_ttl_seconds=settings.upload_url_ttl_seconds,
                    ),
                    confirm_upload=ConfirmCatalogItemUpload(items, storage, clock),
                    get_item=GetCatalogItem(
                        items, storage, download_url_ttl_seconds=settings.download_url_ttl_seconds
                    ),
                    list_items=ListCatalogItems(items),
                    delete_item=DeleteCatalogItem(items, storage),
                )
                session.commit()
            except Exception:
                session.rollback()
                raise
            finally:
                session.close()

        unit_of_work_factory = sql_unit_of_work

    if require_read is None or require_write is None:
        auth_client = AuthServiceClient(settings.auth_service_url)
        require_read = require_read or build_scope_dependency(auth_client, "catalog:read")
        require_write = require_write or build_scope_dependency(auth_client, "catalog:write")

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Idempotent bucket creation so a fresh local stack works with zero
        # manual storage setup. Failure is logged by the adapter and left to
        # /readyz to surface — the API can still serve metadata reads.
        if storage is not None:
            try:
                storage.ensure_bucket()
            except Exception:
                import logging

                logging.getLogger(__name__).exception("could not ensure object storage bucket")
        yield

    app = FastAPI(
        title=settings.service_name,
        version=settings.service_version,
        description="Catalog data layer: item metadata, signed-URL object storage, erasure.",
        lifespan=lifespan,
    )
    register_error_handlers(app)
    app.include_router(build_items_router(unit_of_work_factory, require_read, require_write))

    readiness_session_factory = build_session_factory(settings.database_url)

    @app.get("/health", tags=["ops"])
    def health() -> dict:
        return {
            "status": "ok",
            "service": settings.service_name,
            "version": settings.service_version,
        }

    @app.get("/readyz", tags=["ops"])
    def readyz(response: Response) -> dict:
        results = {}
        try:
            with readiness_session_factory() as session:
                session.execute(text("SELECT 1"))
            results["postgres"] = {"reachable": True}
        except Exception:
            results["postgres"] = {"reachable": False}
        if storage is not None:
            results["object_storage"] = {"reachable": storage.reachable()}
        if auth_client is not None:
            results["auth_service"] = {"reachable": auth_client.health_reachable()}
        all_ok = all(r["reachable"] for r in results.values())
        if not all_ok:
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {
            "status": "ok" if all_ok else "degraded",
            "service": settings.service_name,
            "dependencies": results,
        }

    return app
