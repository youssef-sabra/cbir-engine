"""Redis ingestion-queue producer.

A Redis list is the queue: the producer LPUSHes JSON job payloads; the
ingestion-worker BRPOPs them (at-least-once, FIFO). Kept in messaging/ (not
persistence/) because queue semantics are a distinct concern from data
storage (docs/CLEAN_ARCHITECTURE.md Section 3).

The shared queue key names must match the worker's — they are defined once
here and imported by the worker's contract, but since the worker is a
separate deployable, both sides simply agree on the constant below.
"""

from __future__ import annotations

import json
import logging

import redis

from catalog_service.application.ports import IngestionJob, IngestionQueuePort

logger = logging.getLogger(__name__)

INGESTION_QUEUE_KEY = "cbir:ingest:queue"


class RedisIngestionQueue(IngestionQueuePort):
    def __init__(self, client: redis.Redis, queue_key: str = INGESTION_QUEUE_KEY) -> None:
        self._redis = client
        self._queue_key = queue_key

    def enqueue(self, job: IngestionJob) -> None:
        payload = json.dumps(
            {
                "tenant_id": job.tenant_id,
                "item_id": job.item_id,
                "object_key": job.object_key,
                "attempts": 0,
            }
        )
        self._redis.lpush(self._queue_key, payload)

    def reachable(self) -> bool:
        try:
            return bool(self._redis.ping())
        except redis.RedisError:
            return False
