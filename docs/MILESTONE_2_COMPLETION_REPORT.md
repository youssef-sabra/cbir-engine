# Milestone 2 — Completion Report

**Status: ✅ Completed**
**Scope:** Authentication, Multi-Tenancy & Tenant Management.

---

## 1. What Was Built

`auth-service` — a FastAPI service following the project's Clean Architecture layering
(`docs/CLEAN_ARCHITECTURE.md` Section 3), plus two shared packages every later service reuses.

- **`shared/domain-kernel`** (`cbir_domain_kernel`) — the `TenantId` value object, the one genuinely
  universal domain concept shared across services.
- **`shared/common-libs`** (`cbir_common`) — structured JSON logging, the platform JWT claim contract
  (single source of truth for signer + verifiers), and the gateway-style request-authentication
  dependency resource services use.
- **`services/auth-service`** — tenants, API keys, access tokens, rate limiting:
  - **Tenant lifecycle** via an admin API (manual provisioning, the pre-self-serve path the milestone
    asks for). `scripts/provision_tenant.py` wraps create-tenant + issue-key.
  - **API keys** — issuance with scopes and per-key rate limits; rotation with a configurable grace
    period (old key keeps working until the deadline, so integrations don't break mid-rotation);
    revocation. Keys are `cbir_<id>_<secret>`; only a SHA-256 hash of the secret is stored and the full
    key is shown exactly once (FR4.2).
  - **Access tokens** — short-lived HS256 JWTs (15-min default) exchanged for an API key, signed against
    the shared claim contract.
  - **Gateway-role validation** — `POST /internal/validate` accepts either credential shape (X-API-Key
    or `Authorization: Bearer`), checks the Redis revocation list, enforces the per-key rate limit, and
    returns the `TenantContext` resource services trust. This is the "gateway-level token validation"
    the milestone specifies, implemented as a service endpoint until a real API gateway exists.
  - **Rate limiting** — Redis fixed-window counters keyed per API key (FR4.4, NFR4), failing open with
    loud logging if Redis is unavailable (NFR9).

## 2. Acceptance Criteria — Verified

All three milestone acceptance criteria were verified both by unit tests (in-memory infrastructure) and
against the **live Docker Compose stack** (real PostgreSQL + Redis) on 2026-07-03.

| # | Criterion | Status | Evidence |
|---|---|---|---|
| 1 | A request with an invalid/expired key is rejected with a clear 401 and no downstream service is reached | ✅ | Live: `cbir_bogus_key` → 401; expired key → 401 with `"...expired"` detail. Unit: `test_garbage_key_is_401`, `test_expired_key_is_401`. Resource services only reach a use case *after* `/internal/validate` returns 200. |
| 2 | A tenant exceeding its configured rate limit receives a 429 within expected latency | ✅ | Live: a key limited to 3 req/min returned `200,200,200,429` with a `Retry-After` header. Unit: `TestRateLimiting` (3 tests incl. window reset and per-key independence). |
| 3 | Tenant data isolation: tenant A's key cannot access tenant B's resources under any tested path | ✅ | Live (against catalog-service): tenant B's key → 404 on GET/DELETE of tenant A's item and an empty list; a read-only key → 403 on write. Unit: catalog-service `TestTenantIsolation`. |

Additional verified behaviors: key rotation grace-window semantics; revocation immediately killing
already-issued bearer tokens (via the Redis revocation list); access-token exchange + bearer validation;
unknown-scope rejection at issuance.

## 3. Tests

- `shared/domain-kernel`: 4 passed
- `shared/common-libs`: 4 passed
- `services/auth-service`: 29 passed
- Lint (`ruff format --check`, `ruff check`): clean across all packages.

Unit tests use in-memory fakes exclusively (no PostgreSQL/Redis), keeping them fast and dependency-free,
consistent with the Milestone 1 testing discipline. Real-backend behavior is covered by the live-stack
verification above and, in CI, by the `containerize-and-verify` job's end-to-end smoke test.

## 4. Key Design Decisions

- **auth-service plays the API-gateway role for now.** The architecture validates credentials at the
  gateway; no gateway exists in the local-first stack, so resource services delegate to
  `/internal/validate`. When a real gateway arrives it takes over that call and the `TenantContext`
  contract is unchanged — see `shared/common-libs/cbir_common/auth/`.
- **API-key hashing is SHA-256, not bcrypt/argon2.** The secret is 256 bits of CSPRNG output, so
  key-stretching adds latency on the hot path without adding meaningful security. Documented inline in
  `domain/domain_services`.
- **JWT is HS256 with a shared secret.** Acceptable while one party operates every service; the move to
  asymmetric keys (RS256 + JWKS) is isolated to `jwt_contract` + the signer for when real external trust
  boundaries appear.
- **Per-service Alembic version tables** (`alembic_version_auth`) so each service's migration history is
  independent against the shared local database.

See `services/auth-service/README.md` for the full API surface.
