"""Entrypoint: wire adapters and run the BRPOP consumption loop.

Each job runs in its own DB transaction (unit of work): commit on success,
rollback on failure. The Redis BRPOP loop pulls jobs; the IngestionRunner
decides success/retry/dead-letter.
"""

from __future__ import annotations

import logging
import signal
from contextlib import contextmanager

import redis
from cbir_common.structured_logging import configure_logging
from cbir_common.vectordb import QdrantVectorStore

from ingestion_worker.adapters import (
    AiServiceEmbedderClient,
    RedisIndexVersionBumper,
    S3ObjectDownloader,
    SqlAlchemyItemStore,
)
from ingestion_worker.config import Settings
from ingestion_worker.models import build_session_factory
from ingestion_worker.processor import IngestionProcessor
from ingestion_worker.runner import IngestionRunner

logger = logging.getLogger(__name__)


def build_runner(settings: Settings, redis_client: redis.Redis) -> IngestionRunner:
    session_factory = build_session_factory(settings.database_url)
    downloader = S3ObjectDownloader(
        endpoint_url=settings.s3_endpoint_url,
        access_key=settings.s3_access_key,
        secret_key=settings.s3_secret_key,
        bucket=settings.s3_bucket_name,
        region=settings.s3_region,
    )
    embedder = AiServiceEmbedderClient(settings.ai_service_url)
    vector_store = QdrantVectorStore(settings.qdrant_url)
    index_versions = RedisIndexVersionBumper(redis_client)

    @contextmanager
    def processor_factory():
        session = session_factory()
        try:
            processor = IngestionProcessor(
                items=SqlAlchemyItemStore(session),
                downloader=downloader,
                embedder=embedder,
                vector_store=vector_store,
                index_versions=index_versions,
                dedup_hamming_threshold=settings.dedup_hamming_threshold,
            )
            yield processor
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    return IngestionRunner(
        processor_factory=processor_factory,
        enqueue=lambda payload: redis_client.lpush(settings.queue_key, payload),
        dead_letter=lambda payload: redis_client.lpush(settings.dlq_key, payload),
        settings=settings,
    )


def run_forever(settings: Settings | None = None) -> None:
    settings = settings or Settings()
    configure_logging(settings.service_name)
    redis_client = redis.Redis.from_url(settings.redis_url)
    runner = build_runner(settings, redis_client)

    stopping = {"flag": False}

    def _stop(signum, frame):
        logger.info("shutdown signal received; finishing current job then exiting")
        stopping["flag"] = True

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)

    logger.info("ingestion-worker started; consuming from %s", settings.queue_key)
    while not stopping["flag"]:
        item = redis_client.brpop([settings.queue_key], timeout=settings.poll_timeout_seconds)
        if item is None:
            continue  # idle timeout — loop back and re-check the stop flag
        _, raw_payload = item
        try:
            runner.handle(raw_payload.decode() if isinstance(raw_payload, bytes) else raw_payload)
        except Exception:
            logger.exception("unexpected error handling job; dropping to avoid a hot loop")


if __name__ == "__main__":
    run_forever()
