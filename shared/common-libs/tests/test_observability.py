from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from cbir_common.observability import REQUEST_ID_HEADER, instrument


def _app() -> TestClient:
    app = FastAPI()

    @app.get("/v1/items/{item_id}")
    def get_item(item_id: str):
        return {"id": item_id}

    instrument(app, "test-service")
    return TestClient(app)


def test_metrics_endpoint_exposes_prometheus_exposition():
    client = _app()
    client.get("/v1/items/abc")
    body = client.get("/metrics").text
    assert "http_requests_total" in body
    assert "http_request_duration_seconds" in body
    assert 'service="test-service"' in body


def test_route_template_is_the_metric_label_not_the_raw_path():
    client = _app()
    client.get("/v1/items/one")
    client.get("/v1/items/two")
    body = client.get("/metrics").text
    # One series for the template, not one per id.
    assert 'path="/v1/items/{item_id}"' in body
    assert 'path="/v1/items/one"' not in body


def test_request_id_is_generated_and_echoed():
    client = _app()
    resp = client.get("/v1/items/abc")
    assert resp.headers.get(REQUEST_ID_HEADER)


def test_request_id_is_propagated_when_supplied():
    client = _app()
    resp = client.get("/v1/items/abc", headers={REQUEST_ID_HEADER: "trace-123"})
    assert resp.headers[REQUEST_ID_HEADER] == "trace-123"
