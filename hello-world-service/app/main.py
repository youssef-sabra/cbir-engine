"""
hello-world-service — temporary pipeline-validation service.

Not part of the permanent architecture. See README.md in this directory.
Deliberately has no domain/application/infrastructure layering: there is no
business logic here to layer, so imposing Clean Architecture structure on it
would be ceremony without benefit. Real services (from Milestone 2 onward)
follow the layout documented in docs/CLEAN_ARCHITECTURE.md.
"""

import os
import socket
from dataclasses import dataclass

from fastapi import FastAPI, Response, status

SERVICE_NAME = os.environ.get("SERVICE_NAME", "hello-world-service")
SERVICE_VERSION = os.environ.get("SERVICE_VERSION", "0.1.0")

app = FastAPI(title=SERVICE_NAME, version=SERVICE_VERSION)


@dataclass(frozen=True)
class Dependency:
    """A backing service this container should be able to reach on the
    Compose network. Only TCP reachability is checked here — this endpoint
    exists to prove network wiring, not to exercise each dependency's full
    protocol."""

    name: str
    host_env_var: str
    port_env_var: str
    default_host: str
    default_port: int


DEPENDENCIES = [
    Dependency("postgres", "POSTGRES_HOST", "POSTGRES_PORT", "postgres", 5432),
    Dependency("redis", "REDIS_HOST", "REDIS_PORT", "redis", 6379),
    Dependency("qdrant", "QDRANT_HOST", "QDRANT_HTTP_PORT", "qdrant", 6333),
    Dependency("minio", "MINIO_HOST", "MINIO_API_PORT", "minio", 9000),
]


def _check_tcp(host: str, port: int, timeout_seconds: float = 2.0) -> bool:
    """Best-effort TCP connect check. Returns True if a connection could be
    established, False otherwise. Intentionally simple: this is a pipeline
    smoke test, not a protocol-level health check."""
    try:
        with socket.create_connection((host, port), timeout=timeout_seconds):
            return True
    except OSError:
        return False


@app.get("/health")
def health() -> dict:
    """Liveness check: is the process up at all?"""
    return {
        "status": "ok",
        "service": SERVICE_NAME,
        "version": SERVICE_VERSION,
    }


@app.get("/readyz")
def readyz(response: Response) -> dict:
    """Readiness check: can this container reach every other service on the
    Compose network? This is what actually proves Milestone 1's local stack
    is wired together correctly, not just that this one container started."""
    results = {}
    all_ok = True

    for dep in DEPENDENCIES:
        host = os.environ.get(dep.host_env_var, dep.default_host)
        port = int(os.environ.get(dep.port_env_var, dep.default_port))
        ok = _check_tcp(host, port)
        results[dep.name] = {"reachable": ok, "host": host, "port": port}
        all_ok = all_ok and ok

    if not all_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {
        "status": "ok" if all_ok else "degraded",
        "service": SERVICE_NAME,
        "version": SERVICE_VERSION,
        "dependencies": results,
    }
