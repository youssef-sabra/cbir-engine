# tests/e2e/

Cross-service end-to-end tests — journeys that no single service's own test suite can validate because
they span multiple services (and real backing stores) at once. These run against a **live Docker Compose
stack**, complementing (not replacing) each service's fast, dependency-free unit tests.

## Running

```
docker compose up -d
pip install -r tests/e2e/requirements-dev.txt
pytest tests/e2e -v            # from the repository root
```

If the stack isn't reachable on `:8001` / `:8002`, every test is **skipped** (not failed), so this suite
is safe to include in a plain `pytest` run on a machine that hasn't started the stack. CI exercises the
same journeys via the `containerize-and-verify` job.

## Suites (populated as services come online)

| Folder | Journey | Milestones exercised |
|---|---|---|
| `multi_tenancy_isolation/` | Tenant A's credential cannot reach tenant B's catalog data under any path; scope + invalid-key enforcement | M2 + M3 |
| `ingestion_to_search/` | Signed-URL upload → confirm → download round trip, then right-to-erasure deletion | M3 (embed/search half arrives with M5–M7) |
| `compositional_query/` | Reserved — the compositional-query path (M9) |

Environment overrides: `E2E_AUTH_URL`, `E2E_CATALOG_URL`, `AUTH_ADMIN_TOKEN`.
