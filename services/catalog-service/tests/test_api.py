"""API-level tests for the Milestone 3 storage-foundation slice:

- register -> signed upload URL -> confirm -> downloadable;
- deletion removes the stored object and the metadata (erasure workflow);
- tenant isolation: another tenant cannot see, list, or delete an item.
"""

from tests.conftest import register_item


class TestRegisterAndUploadFlow:
    def test_register_returns_pending_item_and_signed_upload(self, client):
        body = register_item(client, external_id="sku-1")
        assert body["item"]["status"] == "pending_upload"
        assert body["item"]["external_id"] == "sku-1"
        assert body["upload"]["method"] == "PUT"
        assert body["upload"]["headers"] == {"Content-Type": "image/jpeg"}
        assert body["item"]["id"] in body["upload"]["url"]

    def test_confirm_before_upload_conflicts(self, client):
        body = register_item(client)
        response = client.post(f"/v1/items/{body['item']['id']}/confirm")
        assert response.status_code == 409
        assert "signed URL" in response.json()["detail"]

    def test_confirm_after_upload_queues_ingestion_with_size(self, client, world):
        body = register_item(client)
        item_id = body["item"]["id"]
        object_key = f"tenants/{world.auth.tenant_id}/items/{item_id}"
        world.storage.put(object_key, size_bytes=1234)

        response = client.post(f"/v1/items/{item_id}/confirm")
        assert response.status_code == 200
        # Confirmation transitions to QUEUED and enqueues an ingestion job.
        assert response.json()["status"] == "queued"
        assert response.json()["size_bytes"] == 1234
        assert len(world.queue.jobs) == 1
        assert world.queue.jobs[0].item_id == item_id

    def test_download_url_only_after_upload(self, client, world):
        body = register_item(client)
        item_id = body["item"]["id"]
        assert client.get(f"/v1/items/{item_id}").json()["download_url"] is None

        world.storage.put(f"tenants/{world.auth.tenant_id}/items/{item_id}")
        client.post(f"/v1/items/{item_id}/confirm")
        assert "download" in client.get(f"/v1/items/{item_id}").json()["download_url"]

    def test_unsupported_content_type_rejected(self, client):
        response = client.post("/v1/items", json={"content_type": "application/pdf"})
        assert response.status_code == 422

    def test_duplicate_external_id_conflicts(self, client):
        register_item(client, external_id="sku-1")
        response = client.post(
            "/v1/items", json={"content_type": "image/jpeg", "external_id": "sku-1"}
        )
        assert response.status_code == 409


class TestErasure:
    def test_delete_removes_object_and_metadata(self, client, world):
        body = register_item(client)
        item_id = body["item"]["id"]
        object_key = f"tenants/{world.auth.tenant_id}/items/{item_id}"
        world.storage.put(object_key)
        client.post(f"/v1/items/{item_id}/confirm")

        assert client.delete(f"/v1/items/{item_id}").status_code == 204
        # Object gone from storage...
        assert object_key in world.storage.deleted
        assert object_key not in world.storage.objects
        # ...and metadata gone from the repository.
        assert client.get(f"/v1/items/{item_id}").status_code == 404

    def test_delete_unknown_item_is_404(self, client):
        import uuid

        assert client.delete(f"/v1/items/{uuid.uuid4()}").status_code == 404


class TestTenantIsolation:
    def test_other_tenant_cannot_get_list_or_delete(self, client, world):
        import uuid

        body = register_item(client)
        item_id = body["item"]["id"]

        # Same running app, but requests now authenticate as another tenant.
        world.auth.tenant_id = str(uuid.uuid4())

        assert client.get(f"/v1/items/{item_id}").status_code == 404
        assert client.get("/v1/items").json() == []
        assert client.delete(f"/v1/items/{item_id}").status_code == 404
        # And the item still exists for its real owner.
        assert len(world.items.rows) == 1

    def test_listing_only_returns_own_items(self, client, world):
        import uuid

        register_item(client, external_id="mine-1")
        register_item(client, external_id="mine-2")
        first_tenant = world.auth.tenant_id

        world.auth.tenant_id = str(uuid.uuid4())
        register_item(client, external_id="theirs-1")
        assert len(client.get("/v1/items").json()) == 1

        world.auth.tenant_id = first_tenant
        assert len(client.get("/v1/items").json()) == 2


class TestHealth:
    def test_health_is_ok_without_any_backend(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
