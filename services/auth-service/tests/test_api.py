"""API-level tests exercising the Milestone 2 acceptance criteria through the
real FastAPI app (with in-memory infrastructure):

- invalid/expired credentials are rejected with a clear 401;
- exceeding the configured rate limit returns 429;
- rotation keeps the old key working through its grace period only;
- revocation kills both the key and already-issued bearer tokens.
"""

from tests.conftest import ADMIN_HEADERS, create_tenant, issue_key


class TestAdminGuard:
    def test_admin_endpoints_require_admin_token(self, client):
        assert client.post("/admin/tenants", json={"name": "x"}).status_code == 401
        assert (
            client.post(
                "/admin/tenants", json={"name": "x"}, headers={"X-Admin-Token": "wrong"}
            ).status_code
            == 401
        )

    def test_duplicate_tenant_name_conflicts(self, client):
        create_tenant(client, name="acme")
        response = client.post("/admin/tenants", json={"name": "acme"}, headers=ADMIN_HEADERS)
        assert response.status_code == 409


class TestApiKeyValidation:
    def test_valid_key_returns_tenant_context(self, client):
        tenant = create_tenant(client)
        issued = issue_key(client, tenant["id"])
        response = client.post("/internal/validate", headers={"X-API-Key": issued["api_key"]})
        assert response.status_code == 200
        body = response.json()
        assert body["tenant_id"] == tenant["id"]
        assert body["api_key_id"] == issued["metadata"]["id"]
        assert "catalog:read" in body["scopes"]
        assert body["rate_limit"]["limit_per_minute"] == 60  # free-tier default

    def test_garbage_key_is_401(self, client):
        response = client.post("/internal/validate", headers={"X-API-Key": "not-a-key"})
        assert response.status_code == 401
        assert "detail" in response.json()

    def test_wrong_secret_is_401(self, client):
        tenant = create_tenant(client)
        issued = issue_key(client, tenant["id"])
        tampered = issued["api_key"][:-4] + "0000"
        assert client.post("/internal/validate", headers={"X-API-Key": tampered}).status_code == 401

    def test_missing_credentials_is_401(self, client):
        assert client.post("/internal/validate").status_code == 401

    def test_expired_key_is_401(self, client, world):
        tenant = create_tenant(client)
        issued = issue_key(client, tenant["id"], expires_in_days=1)
        world.clock.advance(days=2)
        response = client.post("/internal/validate", headers={"X-API-Key": issued["api_key"]})
        assert response.status_code == 401
        assert "expired" in response.json()["detail"]

    def test_unknown_scope_rejected_at_issuance(self, client):
        tenant = create_tenant(client)
        response = client.post(
            f"/admin/tenants/{tenant['id']}/api-keys",
            json={"scopes": ["catalog:read", "nonsense:scope"]},
            headers=ADMIN_HEADERS,
        )
        assert response.status_code == 422


class TestRateLimiting:
    def test_exceeding_limit_returns_429_with_retry_after(self, client):
        tenant = create_tenant(client)
        issued = issue_key(client, tenant["id"], rate_limit_per_minute=3)
        for _ in range(3):
            ok = client.post("/internal/validate", headers={"X-API-Key": issued["api_key"]})
            assert ok.status_code == 200
        limited = client.post("/internal/validate", headers={"X-API-Key": issued["api_key"]})
        assert limited.status_code == 429
        assert int(limited.headers["Retry-After"]) > 0

    def test_budget_resets_in_next_window(self, client, world):
        tenant = create_tenant(client)
        issued = issue_key(client, tenant["id"], rate_limit_per_minute=1)
        assert (
            client.post("/internal/validate", headers={"X-API-Key": issued["api_key"]}).status_code
            == 200
        )
        assert (
            client.post("/internal/validate", headers={"X-API-Key": issued["api_key"]}).status_code
            == 429
        )
        world.clock.advance(seconds=61)
        assert (
            client.post("/internal/validate", headers={"X-API-Key": issued["api_key"]}).status_code
            == 200
        )

    def test_keys_have_independent_budgets(self, client):
        tenant = create_tenant(client)
        first = issue_key(client, tenant["id"], rate_limit_per_minute=1)
        second = issue_key(client, tenant["id"], rate_limit_per_minute=1)
        assert (
            client.post("/internal/validate", headers={"X-API-Key": first["api_key"]}).status_code
            == 200
        )
        assert (
            client.post("/internal/validate", headers={"X-API-Key": first["api_key"]}).status_code
            == 429
        )
        assert (
            client.post("/internal/validate", headers={"X-API-Key": second["api_key"]}).status_code
            == 200
        )


class TestRotationAndRevocation:
    def test_rotation_issues_new_key_and_old_survives_grace(self, client, world):
        tenant = create_tenant(client)
        original = issue_key(client, tenant["id"])
        rotated = client.post(
            f"/admin/api-keys/{original['metadata']['id']}/rotate", headers=ADMIN_HEADERS
        )
        assert rotated.status_code == 201
        new_key = rotated.json()["api_key"]
        assert new_key != original["api_key"]

        # Both keys work during the grace window...
        for key in (original["api_key"], new_key):
            assert client.post("/internal/validate", headers={"X-API-Key": key}).status_code == 200

        # ...but only the new one after it (grace configured at 3600s in tests).
        world.clock.advance(seconds=3601)
        old = client.post("/internal/validate", headers={"X-API-Key": original["api_key"]})
        assert old.status_code == 401
        assert "grace" in old.json()["detail"]
        assert client.post("/internal/validate", headers={"X-API-Key": new_key}).status_code == 200

    def test_revoked_key_is_401(self, client):
        tenant = create_tenant(client)
        issued = issue_key(client, tenant["id"])
        assert (
            client.post(
                f"/admin/api-keys/{issued['metadata']['id']}/revoke", headers=ADMIN_HEADERS
            ).status_code
            == 200
        )
        response = client.post("/internal/validate", headers={"X-API-Key": issued["api_key"]})
        assert response.status_code == 401
        assert "revoked" in response.json()["detail"]


class TestAccessTokens:
    def test_token_exchange_and_bearer_validation(self, client):
        tenant = create_tenant(client)
        issued = issue_key(client, tenant["id"])
        token_response = client.post("/v1/auth/token", json={"api_key": issued["api_key"]})
        assert token_response.status_code == 200
        token = token_response.json()["access_token"]

        response = client.post("/internal/validate", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
        assert response.json()["tenant_id"] == tenant["id"]

    def test_token_from_invalid_key_is_401(self, client):
        assert client.post("/v1/auth/token", json={"api_key": "cbir_bad_key"}).status_code == 401

    def test_revoking_key_kills_existing_bearer_tokens(self, client):
        tenant = create_tenant(client)
        issued = issue_key(client, tenant["id"])
        token = client.post("/v1/auth/token", json={"api_key": issued["api_key"]}).json()[
            "access_token"
        ]
        client.post(f"/admin/api-keys/{issued['metadata']['id']}/revoke", headers=ADMIN_HEADERS)
        response = client.post("/internal/validate", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 401
        assert "revoked" in response.json()["detail"]

    def test_tampered_token_is_401(self, client):
        response = client.post(
            "/internal/validate", headers={"Authorization": "Bearer not.a.token"}
        )
        assert response.status_code == 401


class TestHealth:
    def test_health_is_ok_without_any_backend(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
