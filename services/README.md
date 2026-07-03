# services/

Request-serving backend services. Each is independently deployable and internally follows the same
four-layer Clean Architecture structure (`docs/CLEAN_ARCHITECTURE.md` Section 3):
`domain/ → application/ → interface_adapters/ → infrastructure/`, wired only in
`entrypoint/composition_root`.

| Service | Status | Milestone | Purpose |
|---|---|---|---|
| `auth-service` | ✅ Implemented | M2 | Tenant identity, API keys, access tokens, rate limiting |
| `catalog-service` | ✅ Implemented | M3 | Catalog item metadata + signed-URL object storage + erasure |
| `query-service` | Reserved | M7 | Image/text/compositional search |
| `tenant-service` | Reserved | later | Tenant billing, usage metering, quota enforcement |
| `admin-service` | Reserved | later | Internal back-office tooling |

Each implemented service has its own `README.md`, `requirements-dev.txt` (installs the `shared/` packages
editable), Alembic migrations run on container start, and a unit-test suite that uses in-memory fakes so
`pytest` needs no running backends. Cross-service journeys are tested in `tests/e2e/`.
