# Runbook — PostgreSQL Backup & Recovery

**Scope:** the local-first Docker Compose stack. This runbook establishes the backup/recovery baseline
required by Milestone 3 (data layer). It is written against the local stack, but the *procedure* — logical
dump, off-host storage, restore-and-verify — is identical against a managed cloud PostgreSQL; only the
mechanics of invoking `pg_dump`/`pg_restore` and where the artifact is stored change.

## What is protected

PostgreSQL is the system of record for every service's metadata: `tenants` and `api_keys`
(auth-service), and `catalog_items`, `embedding_refs`, `feedback`, `usage_records`, `adapter_versions`
(catalog-service). Object storage (MinIO/S3) holds the raw image bytes and is backed up by the storage
layer's own replication/versioning in production; the raw-bytes backup strategy is tracked with the
ingestion milestone. This runbook covers the relational system of record.

## Objectives (local baseline)

| Objective | Target (local baseline) | Rationale |
|---|---|---|
| **RPO** (max acceptable data loss) | ≤ 24h with daily dumps; ≤ the interval you schedule | A logical dump captures a consistent snapshot at dump time |
| **RTO** (max acceptable time to restore) | ≤ 15 min for the local dataset | `pg_restore` of a small logical dump completes in seconds-to-minutes |

Production RPO/RTO tighten via continuous archiving (WAL) + point-in-time recovery on the managed
database; that is a deployment-milestone concern, explicitly out of scope here.

## Backing up

```
make db-backup
# or directly:
./scripts/db_backup.sh
```

Produces a timestamped custom-format dump under `backups/` (gitignored), e.g.
`backups/cbir-20260703-120000.dump`. The custom format (`pg_dump -Fc`) is compressed and restorable
selectively. `pg_dump` runs inside the `postgres` container, so no local PostgreSQL client is needed.

**Off-host storage:** for any real use, copy the dump off the machine (in production, the dump lands in an
object-storage bucket in a different failure domain than the database). Locally, copying `backups/` to
another disk is sufficient to rehearse the discipline.

## Restoring

```
make db-restore FILE=backups/cbir-20260703-120000.dump
# or directly:
./scripts/db_restore.sh backups/cbir-20260703-120000.dump
```

`pg_restore --clean --if-exists` drops and recreates each object from the dump, so it is safe to run
against an existing database. Because each service tracks its own Alembic version table
(`alembic_version_auth`, `alembic_version_catalog`), a restored database reports the correct migration
state and services will not attempt to re-run already-applied migrations on next start.

## Verified recovery drill (2026-07-03)

The following drill was executed against the live local stack to prove the runbook works, not just that
the scripts exist:

1. Provisioned a tenant and issued an API key; registered a catalog item — establishing known rows in
   both `tenants`/`api_keys` and `catalog_items`.
2. `make db-backup` → produced a dump artifact.
3. **Simulated data loss:** deleted the tenant row (cascading to its API keys) and the catalog item.
4. Confirmed the rows were gone (the API key no longer validated; the item 404'd).
5. `make db-restore FILE=<dump>`.
6. **Verified recovery:** the tenant, API key, and catalog item were all present again; the previously
   deleted API key validated successfully once more.

See `docs/MILESTONE_3_COMPLETION_REPORT.md` for the captured evidence of this drill.

## Scheduling (production note)

In the local stack, backups are run on demand. In production this becomes a scheduled job (cron/CronJob)
writing to off-host object storage with a retention policy, plus WAL archiving for point-in-time
recovery. That automation is deliberately deferred to the deployment milestone — this runbook establishes
the procedure and proves it recovers data.
