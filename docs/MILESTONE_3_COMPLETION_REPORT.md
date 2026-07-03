# Milestone 3 — Completion Report

**Status: ✅ Completed**
**Scope:** Data Layer & Storage Foundation.

---

## 1. What Was Built

`catalog-service` — the persistent storage layer for catalog metadata and raw images, following the
project's Clean Architecture layering. It exposes the register → upload → confirm → download → delete
lifecycle and owns the full Milestone 3 database schema.

- **PostgreSQL schema** (Alembic, version table `alembic_version_catalog`): `catalog_items`,
  `embedding_refs`, `feedback`, `usage_records`, `adapter_versions` — the complete set named in the
  milestone plan. `usage_records` and `adapter_versions` will re-home to tenant-service and ai-service
  respectively when those exist; a documented, mechanical migration-package move (the tables don't
  change).
- **pgvector extension** enabled by the migration (`CREATE EXTENSION IF NOT EXISTS vector`), readying
  PostgreSQL for small-tenant vector workloads per `docs/TECH_STACK.md`.
- **Object storage via signed URLs** (S3 API / boto3, against MinIO locally): clients upload and download
  image bytes directly to/from storage using short-lived presigned URLs — bytes never transit the
  service. The S3 adapter works identically against any S3-compatible store (Milestone 1's open-protocol
  principle).
- **Right-to-erasure deletion** (NFR13): deleting an item removes the stored object first, then the
  metadata row; `embedding_refs` and `feedback` cascade with it via FK constraints.
- **Backup & recovery baseline**: `scripts/db_backup.sh` / `db_restore.sh`, `make db-backup` /
  `db-restore`, and `docs/RUNBOOK_BACKUP_RESTORE.md` documenting the procedure, RPO/RTO, and the
  executed recovery drill.

All catalog endpoints authenticate through auth-service's gateway-role endpoint (writes need
`catalog:write`, reads `catalog:read`); every repository operation is tenant-scoped by interface
signature, making cross-tenant access structurally inexpressible (FR4.1).

## 2. Acceptance Criteria — Verified

Verified by unit tests (in-memory fakes) and against the **live Docker Compose stack** (real PostgreSQL +
MinIO + auth-service) on 2026-07-03.

| # | Criterion | Status | Evidence |
|---|---|---|---|
| 1 | An image can be uploaded to object storage via signed URL and its metadata correctly persisted to PostgreSQL | ✅ | Live: registered an item (row persisted, status `pending_upload`), PUT 2048 bytes to the signed MinIO URL, confirmed (status → `uploaded`, `size_bytes=2048` persisted), fetched the same 2048 bytes back via a signed download URL. |
| 2 | A simulated data-loss scenario is recoverable within the defined RTO using the documented runbook | ✅ | Live drill: baseline (key validates) → `db_backup.sh` → deleted tenant A (cascade removed its API keys; key now 401) → `db_restore.sh` → key validates again (200) and both catalog items for the tenant were recovered. Completed in well under the 15-min local RTO. |
| 3 | A test deletion request removes both the object storage file and associated metadata rows | ✅ | Live: after DELETE (→204), the metadata row 404'd and the previously valid signed download URL returned NoSuchKey — the object was genuinely gone from MinIO, not just the row. |

Additional verified behaviors: pgvector extension present (`SELECT extname FROM pg_extension` →
`vector`); all seven data-layer tables migrated; duplicate `external_id` rejected (409); unsupported
content type rejected (422); confirm-before-upload rejected (409).

## 3. Tests

- `services/catalog-service`: 11 passed
- Lint (`ruff format --check`, `ruff check`): clean.
- Full repository sweep at time of completion: **48 unit tests passing** across all four Python packages;
  13 live M2/M3 acceptance checks + 5 storage/erasure checks + the recovery drill, all green.

## 4. Key Design Decisions

- **Two-step upload (register → confirm) with client-direct signed URLs.** The service issues a presigned
  PUT, the client uploads bytes straight to storage, then confirms; the service verifies the object
  exists (via `HEAD`) and records its size. This keeps large image bytes off the API's request path
  (matching the ingestion design Milestone 4 builds on) and means the metadata row can never claim an
  object that isn't actually stored.
- **Split S3 endpoints for signing vs. service traffic.** SigV4 signatures cover the Host header, so
  signed URLs must embed the endpoint the *client* will reach (`localhost:9000`), while the service
  itself talks to MinIO over the Compose network (`minio:9000`). Two boto3 clients handle this; in
  production both collapse to one public endpoint.
- **No cross-service-package foreign keys.** `catalog_items.tenant_id` is indexed but not FK'd to
  auth-service's `tenants` table — cross-package FKs would couple the services' deploy order. Tenant
  validity is enforced at the application layer (every request's tenant_id comes from auth-service
  validation first).
- **Erasure deletes the object before the rows**, and object deletion is idempotent, so a failure
  mid-way is safely retryable and never leaves an orphaned object with no metadata pointing at it.

See `services/catalog-service/README.md` for the full API surface and schema-ownership table.
