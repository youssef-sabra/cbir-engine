"""Milestone 4 ingestion behaviors on the catalog-service side: batch
registration, enqueue-on-confirm, and job-status tracking/filtering."""

from __future__ import annotations

from tests.conftest import register_item


class TestBatchRegister:
    def test_batch_registers_all_items_with_upload_urls(self, client):
        body = {"items": [{"content_type": "image/jpeg", "metadata": {"i": n}} for n in range(25)]}
        r = client.post("/v1/items/batch", json=body)
        assert r.status_code == 201
        items = r.json()["items"]
        assert len(items) == 25
        assert all(i["item"]["status"] == "pending_upload" for i in items)
        assert all(i["upload"]["method"] == "PUT" for i in items)
        # distinct object keys / ids
        assert len({i["item"]["id"] for i in items}) == 25

    def test_batch_rejects_intra_batch_duplicate_external_id(self, client):
        body = {
            "items": [
                {"content_type": "image/jpeg", "external_id": "dup"},
                {"content_type": "image/jpeg", "external_id": "dup"},
            ]
        }
        assert client.post("/v1/items/batch", json=body).status_code == 409

    def test_empty_batch_rejected(self, client):
        assert client.post("/v1/items/batch", json={"items": []}).status_code == 422


class TestEnqueueOnConfirm:
    def test_confirm_enqueues_job_and_sets_queued(self, client, world):
        body = register_item(client)
        item_id = body["item"]["id"]
        world.storage.put(f"tenants/{world.auth.tenant_id}/items/{item_id}")
        client.post(f"/v1/items/{item_id}/confirm")
        assert [j.item_id for j in world.queue.jobs] == [item_id]

    def test_confirm_without_object_does_not_enqueue(self, client, world):
        body = register_item(client)
        item_id = body["item"]["id"]
        assert client.post(f"/v1/items/{item_id}/confirm").status_code == 409
        assert world.queue.jobs == []


class TestJobStatusTracking:
    def test_list_filters_by_status(self, client, world):
        # one item confirmed (queued), one left pending
        queued = register_item(client, external_id="q")
        register_item(client, external_id="p")
        world.storage.put(f"tenants/{world.auth.tenant_id}/items/{queued['item']['id']}")
        client.post(f"/v1/items/{queued['item']['id']}/confirm")

        pending = client.get("/v1/items", params={"status": "pending_upload"}).json()
        queued_list = client.get("/v1/items", params={"status": "queued"}).json()
        assert {i["external_id"] for i in pending} == {"p"}
        assert {i["external_id"] for i in queued_list} == {"q"}

    def test_unknown_status_filter_is_422(self, client):
        assert client.get("/v1/items", params={"status": "nonsense"}).status_code == 422

    def test_item_exposes_ingestion_fields(self, client):
        body = register_item(client)
        item = client.get(f"/v1/items/{body['item']['id']}").json()["item"]
        # New Milestone 4 fields are present (null until the worker runs).
        assert item["duplicate_of_id"] is None
        assert item["failure_reason"] is None
        assert item["indexed_at"] is None
