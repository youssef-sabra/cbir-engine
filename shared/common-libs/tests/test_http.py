from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from cbir_common.http import add_security_headers, configure_cors


def _app(cors: str | None = None) -> TestClient:
    app = FastAPI()

    @app.get("/x")
    def x():
        return {"ok": True}

    add_security_headers(app)
    if cors is not None:
        configure_cors(app, cors)
    return TestClient(app)


def test_security_headers_present():
    resp = _app().get("/x")
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
    assert resp.headers["X-Frame-Options"] == "DENY"
    assert resp.headers["Referrer-Policy"] == "no-referrer"


def test_cors_wildcard_allows_cross_origin():
    resp = _app(cors="*").get("/x", headers={"Origin": "http://dash.local"})
    assert resp.headers.get("access-control-allow-origin") == "*"


def test_cors_restricted_to_specific_origin():
    resp = _app(cors="http://dash.local").get("/x", headers={"Origin": "http://dash.local"})
    assert resp.headers.get("access-control-allow-origin") == "http://dash.local"
