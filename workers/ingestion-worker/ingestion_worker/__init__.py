"""ingestion-worker — the asynchronous ingestion pipeline (Milestone 4).

Consumes ingestion jobs from the Redis queue that catalog-service produces,
and for each item: downloads the bytes, embeds them via ai-service, runs
perceptual-hash deduplication, and either indexes the vector into Qdrant (and
records the embedding reference) or marks the item a duplicate. Failures are
retried with backoff and finally dead-lettered.

The worker writes directly to PostgreSQL and the vector store, per the
architecture (Section 8: "Ingestion Queue Workers ... write to the Vector DB
and PostgreSQL"). It is a separate deployable, scaling on queue depth
independently of the request-serving services.
"""
