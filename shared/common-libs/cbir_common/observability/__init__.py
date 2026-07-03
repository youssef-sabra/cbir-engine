"""Shared observability: Prometheus metrics, request-id/trace propagation, and
structured request logging — applied identically across every FastAPI service
(Milestone 10). Purely operational, no business logic (fits `shared/`).

`instrument(app, service_name)` is the one call each service's composition
root makes: it adds a metrics middleware, a `/metrics` endpoint, and a
request-id middleware that stamps every log line and response with a trace id.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)
from starlette.middleware.base import BaseHTTPMiddleware

REQUEST_ID_HEADER = "X-Request-ID"

# Latency buckets tuned to the NFR targets (P95 300ms simple, 1.5s reranked).
_LATENCY_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.2, 0.3, 0.5, 1.0, 1.5, 3.0, 10.0)


def build_registry() -> CollectorRegistry:
    return CollectorRegistry()


class MetricsMiddleware(BaseHTTPMiddleware):
    """Records request count, latency, and in-flight requests, labelled by
    method / route-template / status. The route TEMPLATE (not the raw path) is
    used as the label to keep cardinality bounded — `/v1/items/{item_id}`, not
    a distinct series per id."""

    def __init__(self, app, service_name: str, registry: CollectorRegistry) -> None:
        super().__init__(app)
        self._requests = Counter(
            "http_requests_total",
            "Total HTTP requests.",
            ["service", "method", "path", "status"],
            registry=registry,
        )
        self._latency = Histogram(
            "http_request_duration_seconds",
            "HTTP request latency.",
            ["service", "method", "path"],
            buckets=_LATENCY_BUCKETS,
            registry=registry,
        )
        self._in_progress = Gauge(
            "http_requests_in_progress",
            "In-flight HTTP requests.",
            ["service", "method"],
            registry=registry,
        )
        self._service = service_name

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        method = request.method
        self._in_progress.labels(self._service, method).inc()
        start = time.perf_counter()
        status = "500"
        try:
            response = await call_next(request)
            status = str(response.status_code)
            return response
        finally:
            elapsed = time.perf_counter() - start
            path = _route_template(request)
            self._requests.labels(self._service, method, path, status).inc()
            self._latency.labels(self._service, method, path).observe(elapsed)
            self._in_progress.labels(self._service, method).dec()


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Assigns/propagates a request id and echoes it on the response. This is
    the lightweight distributed-trace correlation id: a client (or the gateway)
    can pass X-Request-ID and it flows through logs and downstream calls."""

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get(REQUEST_ID_HEADER) or uuid.uuid4().hex
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers[REQUEST_ID_HEADER] = request_id
        return response


def instrument(app: FastAPI, service_name: str) -> CollectorRegistry:
    """Add metrics + request-id middleware and a /metrics endpoint. Returns the
    registry so a service can register extra collectors on it."""
    registry = build_registry()
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(MetricsMiddleware, service_name=service_name, registry=registry)

    @app.get("/metrics", include_in_schema=False)
    def metrics() -> Response:
        return Response(generate_latest(registry), media_type=CONTENT_TYPE_LATEST)

    app.state.metrics_registry = registry
    return registry


def _route_template(request: Request) -> str:
    route = request.scope.get("route")
    if route is not None and getattr(route, "path", None):
        return route.path
    return "unmatched"
