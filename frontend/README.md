# frontend/

The customer-facing web surface (Milestone 11).

## `dashboard/`

A **build-free** self-serve dashboard: plain HTML + CSS + vanilla JS, served by nginx (no npm toolchain).
It is "just another API consumer" — it calls the same public REST endpoints as the SDK and external
customers (dogfooding), per the architecture's frontend design.

Features:
- **Connect** — paste an API key (from `python scripts/provision_tenant.py`) and the catalog/query URLs.
- **Catalog** — upload an image (register → signed-URL PUT → confirm) and list items with their ingestion
  status.
- **Search playground** — text, image, and compositional (image + modifier) search with metadata filters,
  showing scores and whether the result was cached/reranked.

Runs at http://localhost:3001 via `docker compose up`. The catalog and query services enable CORS
(`CORS_ALLOW_ORIGINS`, `*` in local dev) so the browser can call them.

> A full React SPA with signup/billing is the production evolution; this build-free dashboard delivers the
> self-serve playground and catalog management without a heavy toolchain, keeping the local-first stack
> `docker compose up`-simple. Interactive API reference is available per-service at `/docs` (FastAPI
> Swagger UI) and `/openapi.json`.

## Dashboard UI workflow notes

The dashboard is organized around three user-facing steps:

1. **Connect**
   - Paste the tenant API key.
   - Confirm the Catalog Service and Query Service URLs.
   - Save the connection in browser local storage for local testing.

2. **Catalog**
   - Upload an image.
   - Add optional JSON metadata.
   - Refresh the catalog list to check ingestion status.

3. **Search**
   - Run text-to-image search.
   - Run image-to-image search.
   - Add an optional modifier for compositional search.
   - Apply optional metadata filters and adjust top-K result count.

These notes describe the dashboard user flow only. They do not change API contracts,
backend behavior, search logic, ingestion behavior, or service configuration.
