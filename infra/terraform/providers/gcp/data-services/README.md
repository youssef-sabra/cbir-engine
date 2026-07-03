# providers/gcp/data-services/

**Status: reserved, not yet implemented.**

Will implement the contract defined in `infra/terraform/modules/data-services/` once Milestone 3
(managed PostgreSQL/Redis) and Milestone 6 (vector database scale-out) are reached. Anticipated resources:

- `google_sql_database_instance` (Cloud SQL for PostgreSQL, with `pgvector` enabled)
- `google_redis_instance` (Memorystore)
- Qdrant/Milvus deployment or managed equivalent, per the scale-threshold migration runbook described in
  `docs/ARCHITECTURE.md` Section 6

Locally, all of these are represented by the `postgres`, `redis`, and `qdrant` services in the root
`docker-compose.yml` — see the root `README.md` for the local/production equivalence table.
