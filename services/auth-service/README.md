# auth-service

Tenant identity, API key lifecycle, access-token issuance, and rate limiting (Milestone 2).
Every other service depends on this one for isolation and security.

## Responsibilities

- **Tenant lifecycle** — manual provisioning via the admin API (self-serve signup arrives with the
  dashboard milestone).
- **API keys** — issuance, scoping, rotation (with a grace period so integrations don't break
  mid-rotation), revocation. Keys are `cbir_<key-id>_<secret>`; only a SHA-256 hash of the secret is
  stored, and the full key is shown exactly once at issuance.
- **Access tokens** — short-lived HS256 JWTs (15 min default) exchanged for an API key at
  `POST /v1/auth/token`, signed against the shared claim contract in `cbir_common.auth.jwt_contract`.
- **The gateway role** — `POST /internal/validate` validates either credential shape (X-API-Key or
  `Authorization: Bearer`), checks the Redis revocation list, enforces the per-key rate limit, and
  returns the `TenantContext` resource services trust. When a real API gateway is introduced, it takes
  over this call; nothing else changes.
- **Rate limiting** — Redis fixed-window counters per API key (FR4.4). Fails open with loud logging if
  Redis is down (NFR9: degrade, don't die).

## API surface

| Method & path | Auth | Purpose |
|---|---|---|
| `POST /admin/tenants` | admin token | Create tenant |
| `GET /admin/tenants`, `GET /admin/tenants/{id}` | admin token | Inspect tenants |
| `POST /admin/tenants/{id}/api-keys` | admin token | Issue API key (full key returned once) |
| `GET /admin/tenants/{id}/api-keys` | admin token | List key metadata (never secrets) |
| `POST /admin/api-keys/{id}/rotate` | admin token | Rotate; old key valid until grace deadline |
| `POST /admin/api-keys/{id}/revoke` | admin token | Revoke key + kill its bearer tokens |
| `POST /v1/auth/token` | API key in body | Exchange API key for a bearer token |
| `POST /internal/validate` | X-API-Key or Bearer | Gateway-role validation (200/401/429) |
| `GET /health`, `GET /readyz` | none | Liveness / readiness |

The admin API is guarded by a shared secret (`AUTH_ADMIN_TOKEN`, header `X-Admin-Token`) — deliberate
minimal internal tooling per the Milestone 2 plan, replaced by real operator identity at the dashboard
milestone. `scripts/provision_tenant.py` at the repository root wraps the common "create tenant + issue
key" flow.

## Layout

Clean Architecture per `docs/CLEAN_ARCHITECTURE.md` Section 3, inside the `auth_service` package:
`domain/` → `application/` → `interface_adapters/` → `infrastructure/`, wired only in
`entrypoint/composition_root`. Migrations: Alembic, `alembic upgrade head` on container start,
version table `alembic_version_auth` (each service tracks its own migration history against the
shared local database).

## Development

```
pip install -r requirements-dev.txt   # from this directory
ruff format --check . && ruff check .
python -m pytest -v
```

Unit tests use in-memory fakes exclusively — no database or Redis required. End-to-end behavior
against real backends is covered by `tests/e2e/` at the repository root.
