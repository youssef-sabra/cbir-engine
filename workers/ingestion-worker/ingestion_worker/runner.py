"""Queue-consumption loop, retry/backoff, and dead-lettering.

Delivery is at-least-once: a job is only removed from the queue once it has
been processed (or dead-lettered). Transient failures are retried up to
`max_attempts` with a backoff re-enqueue; permanent failures and exhausted
retries go to the dead-letter queue and the item is marked FAILED with a
reason. This is the testable policy layer; the actual Redis loop is
`run_forever`.
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass

from ingestion_worker import metrics
from ingestion_worker.config import Settings
from ingestion_worker.ports import PermanentError, TransientError
from ingestion_worker.processor import IngestionProcessor, ProcessResult

logger = logging.getLogger(__name__)

# A unit of work yields a processor bound to a fresh DB session/transaction.
ProcessorFactory = Callable[[], AbstractContextManager[IngestionProcessor]]


@dataclass
class JobDisposition:
    action: str  # "done" | "retry" | "dead_letter"
    requeue_payload: str | None = None
    dead_letter_payload: str | None = None


class IngestionRunner:
    def __init__(
        self,
        processor_factory: ProcessorFactory,
        enqueue: Callable[[str], None],
        dead_letter: Callable[[str], None],
        settings: Settings,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._processor_factory = processor_factory
        self._enqueue = enqueue
        self._dead_letter = dead_letter
        self._settings = settings
        self._sleep = sleep

    def handle(self, raw_payload: str) -> JobDisposition:
        """Process one raw queue payload and decide its disposition, recording
        the outcome and duration as metrics (Milestone 10)."""
        with metrics.JOB_DURATION.time():
            disposition = self._handle(raw_payload)
        metrics.record(disposition.action)
        return disposition

    def _handle(self, raw_payload: str) -> JobDisposition:
        """The disposition decision. Pure enough to unit-test every branch
        (success/duplicate/retry/DLQ)."""
        try:
            job = json.loads(raw_payload)
            item_id = job["item_id"]
        except (json.JSONDecodeError, KeyError, TypeError):
            logger.error("malformed ingestion payload; dead-lettering: %r", raw_payload)
            self._dead_letter(raw_payload)
            return JobDisposition(action="dead_letter", dead_letter_payload=raw_payload)

        attempts = int(job.get("attempts", 0))
        try:
            result = self._run_once(item_id)
            logger.info("ingested item %s -> %s", item_id, result.outcome)
            return JobDisposition(action="done")
        except PermanentError as exc:
            self._fail(item_id, f"permanent: {exc}")
            self._dead_letter(raw_payload)
            return JobDisposition(action="dead_letter", dead_letter_payload=raw_payload)
        except (TransientError, Exception) as exc:  # noqa: BLE001 - last-resort safety net
            attempts += 1
            if attempts >= self._settings.max_attempts:
                reason = f"failed after {attempts} attempts: {exc}"
                self._fail(item_id, reason)
                self._dead_letter(raw_payload)
                return JobDisposition(action="dead_letter", dead_letter_payload=raw_payload)
            job["attempts"] = attempts
            requeue = json.dumps(job)
            self._sleep(self._settings.retry_backoff_seconds * attempts)
            self._enqueue(requeue)
            logger.warning("retrying item %s (attempt %d): %s", item_id, attempts, exc)
            return JobDisposition(action="retry", requeue_payload=requeue)

    def _run_once(self, item_id: str) -> ProcessResult:
        with self._processor_factory() as processor:
            return processor.process(item_id)

    def _fail(self, item_id: str, reason: str) -> None:
        try:
            with self._processor_factory() as processor:
                processor.fail(item_id, reason)
        except Exception:
            logger.exception("could not mark item %s failed", item_id)
