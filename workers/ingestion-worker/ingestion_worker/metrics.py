"""Prometheus metrics for the ingestion worker (Milestone 10).

The worker has no HTTP API, so it exposes metrics on a dedicated port via
prometheus_client's exposition server. Counters work whether or not that
server is running, so the runner can record unconditionally and unit tests
stay oblivious to Prometheus.
"""

from __future__ import annotations

import logging

from prometheus_client import Counter, Gauge, Histogram, start_http_server

logger = logging.getLogger(__name__)

JOBS_TOTAL = Counter(
    "ingestion_jobs_total",
    "Ingestion jobs handled, by final disposition.",
    ["result"],  # done | retry | dead_letter
)
JOB_DURATION = Histogram(
    "ingestion_job_duration_seconds",
    "Time to handle one ingestion job.",
)
QUEUE_DEPTH = Gauge(
    "ingestion_queue_depth",
    "Current queue depth.",
    ["queue"],  # main | dlq
)


def record(result: str) -> None:
    JOBS_TOTAL.labels(result).inc()


def start_metrics_server(port: int) -> None:
    try:
        start_http_server(port)
        logger.info("worker metrics exposed on :%d/metrics", port)
    except OSError:
        logger.warning("could not start metrics server on :%d", port, exc_info=True)
