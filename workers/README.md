# workers/

Asynchronous background processing, scaling on queue depth independently of the request-serving services
and off the query hot path.

| Worker | Status | Milestone | Purpose |
|---|---|---|---|
| `ingestion-worker` | ✅ Implemented | M4 | Consume the Redis ingestion queue: download bytes → embed (ai-service) → pHash dedup → index into Qdrant → update PostgreSQL. Retry/backoff + dead-letter queue. |
| `reindex-worker` | Reserved | later | Full/partial catalog re-index, model-version migrations |
| `notification-worker` | Reserved | later | Webhook / event delivery |

`ingestion-worker` is a queue consumer (no HTTP port). Its processor and runner are dependency-injected and
infrastructure-free, so the dedup/index decision and the retry/dead-letter policy are unit-tested entirely
with fakes (`pytest` needs no PostgreSQL/Redis/Qdrant/MinIO/ai-service). It writes directly to PostgreSQL
and the vector store per the architecture; catalog-service's Alembic migrations remain the single source of
truth for the schema it mirrors.
