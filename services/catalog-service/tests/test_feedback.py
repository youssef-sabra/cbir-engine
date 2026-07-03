"""Relevance-feedback endpoint (FR3.1 / Milestone 9 fast-follow)."""

from __future__ import annotations

import uuid

from tests.conftest import register_item


def test_feedback_recorded_for_own_item(client, world):
    item = register_item(client)["item"]
    r = client.post(
        "/v1/feedback",
        json={"item_id": item["id"], "query_ref": "q-123", "relevant": True},
    )
    assert r.status_code == 201
    assert r.json()["status"] == "recorded"
    assert len(world.feedback.rows) == 1
    assert world.feedback.rows[0][2] == "q-123"


def test_feedback_for_unknown_item_is_404(client, world):
    r = client.post(
        "/v1/feedback",
        json={"item_id": str(uuid.uuid4()), "query_ref": "q", "relevant": False},
    )
    assert r.status_code == 404
    assert world.feedback.rows == []


def test_feedback_for_other_tenant_item_is_404(client, world):
    item = register_item(client)["item"]
    world.auth.tenant_id = str(uuid.uuid4())  # become a different tenant
    r = client.post(
        "/v1/feedback",
        json={"item_id": item["id"], "query_ref": "q", "relevant": True},
    )
    assert r.status_code == 404
    assert world.feedback.rows == []
