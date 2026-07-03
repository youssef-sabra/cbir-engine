"""
Unit tests for hello-world-service.

Note: test_readyz_reports_unreachable_dependencies_without_crashing
deliberately does NOT require Postgres/Redis/Qdrant/MinIO to actually be
running. Unit tests must not depend on the Docker Compose stack being up —
that end-to-end wiring is instead verified by the CI pipeline's
"verify application starts correctly" stage (see .github/workflows/ci.yml
and Makefile's `ci-local` target), which runs against the real Compose stack.
This separation keeps `pytest` fast and runnable with zero external
dependencies, which is exactly what the CI "run tests" step should be.
"""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_ok():
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "service" in body
    assert "version" in body


def test_readyz_reports_unreachable_dependencies_without_crashing():
    # In the unit-test environment, none of postgres/redis/qdrant/minio are
    # reachable at their default hostnames, so we expect a 503 with a clear
    # per-dependency breakdown -- not an exception.
    response = client.get("/readyz")
    assert response.status_code in (200, 503)
    body = response.json()
    assert body["status"] in ("ok", "degraded")
    assert set(body["dependencies"].keys()) == {"postgres", "redis", "qdrant", "minio"}
    for dep_result in body["dependencies"].values():
        assert "reachable" in dep_result
