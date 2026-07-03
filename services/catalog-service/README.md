# catalog-service

The data layer & storage foundation (Milestone 3): catalog item metadata in PostgreSQL, raw image
bytes in S3-compatible object storage via signed URLs, and the right-to-erasure deletion workflow.
Milestone 4 extends this service with the asynchronous ingestion pipeline (dedup, queue, workers).

## The storage flow

1. `POST /v1/items` — registers metadata (status `pending_upload`) and returns a **signed PUT URL**;
   the client uploads image bytes directly to object storage, never through this service.
2. `POST /v1/items/{id}/confirm` — verifies the object actually exists in storage, records its size,
   and marks the item `uploaded`.
3. `GET /v1/items/{id}` — item metadata plus a short-lived **signed download URL** once uploaded.
4. `DELETE /v1/items/{id}` — the erasure workflow (NFR13): deletes the stored object, then the
   metadata row; embedding references and feedback rows cascade with it.

All endpoints require a platform credential (X-API-Key or Bearer token) validated through
auth-service's gateway-role endpoint; writes need the `catalog:write` scope, reads `catalog:read`.
Every query is tenant-scoped by repository-interface signature — cross-tenant access is structurally
inexpressible (FR4.1).

## Schema ownership (Milestone 3)

This service's Alembic package (version table `alembic_version_catalog`) owns:

| Table | Notes |
|---|---|
| `catalog_items` | Item metadata; JSONB `metadata` for tenant attributes (FR1.6); `phash` reserved for M4 dedup |
| `embedding_refs` | Vector provenance pointers, cascade-delete with their item (populated from M5/6) |
| `feedback` | Relevance feedback (FR3.1), cascade-delete with their item |
| `usage_records` | Metering events — re-homes to tenant-service when it exists |
| `adapter_versions` | Per-tenant fine-tune versions — re-homes to ai-service at M5 |

The migration also enables the **pgvector extension**. `tenants`/`api_keys` belong to auth-service's
migration package; no cross-service-package foreign keys are declared (application-layer integrity,
so services stay independently deployable).

## Local endpoint notes

Signed URLs embed the endpoint the *client* will reach: locally that is the host-published MinIO port
(`S3_PRESIGN_ENDPOINT_URL=http://localhost:9000`), while the service itself reaches MinIO as
`http://minio:9000` on the Compose network. In production both collapse to the same public endpoint.

## Development

```
pip install -r requirements-dev.txt   # from this directory
ruff format --check . && ruff check .
python -m pytest -v
```

Unit tests use in-memory fakes exclusively. The full signed-URL round trip against real MinIO and
PostgreSQL is covered by `tests/e2e/` at the repository root.
