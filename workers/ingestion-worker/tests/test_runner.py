"""Runner tests: retry/backoff and dead-lettering policy (Milestone 4:
'malformed image fails gracefully, lands in the DLQ, does not crash the pool')."""

from __future__ import annotations

import json

from ingestion_worker.runner import IngestionRunner


def _runner(world, settings):
    requeued: list[str] = []
    dlq: list[str] = []
    runner = IngestionRunner(
        processor_factory=world.processor_factory,
        enqueue=requeued.append,
        dead_letter=dlq.append,
        settings=settings,
        sleep=lambda _s: None,
    )
    return runner, requeued, dlq


def _job(item_id: str, attempts: int = 0) -> str:
    return json.dumps({"item_id": item_id, "attempts": attempts})


def test_successful_job_is_done(world, settings):
    world.seed_item("i1", "t1", b"img-a", phash="0000000000000000", vector=[1.0, 0.0])
    runner, requeued, dlq = _runner(world, settings)
    disp = runner.handle(_job("i1"))
    assert disp.action == "done"
    assert requeued == [] and dlq == []
    assert world.items.items["i1"].status == "indexed"


def test_permanent_error_dead_letters_immediately(world, settings):
    world.seed_item("i1", "t1", b"img-a", phash="0000000000000000")
    world.embedder.raise_permanent = True
    runner, requeued, dlq = _runner(world, settings)
    disp = runner.handle(_job("i1"))
    assert disp.action == "dead_letter"
    assert len(dlq) == 1 and requeued == []
    assert world.items.items["i1"].status == "failed"
    assert "permanent" in world.items.failed["i1"]


def test_transient_error_retries_then_dead_letters(world, settings):
    world.seed_item("i1", "t1", b"img-a", phash="0000000000000000")
    world.downloader.raise_transient = True
    runner, requeued, dlq = _runner(world, settings)

    # attempt 0 -> retry (requeued with attempts=1)
    disp = runner.handle(_job("i1", attempts=0))
    assert disp.action == "retry"
    assert json.loads(requeued[-1])["attempts"] == 1

    # attempts reach max (3) -> dead-letter + FAILED
    disp = runner.handle(_job("i1", attempts=2))
    assert disp.action == "dead_letter"
    assert len(dlq) == 1
    assert world.items.items["i1"].status == "failed"


def test_malformed_payload_dead_letters_without_crashing(world, settings):
    runner, requeued, dlq = _runner(world, settings)
    disp = runner.handle("this is not json")
    assert disp.action == "dead_letter"
    assert dlq == ["this is not json"]


def test_transient_then_success_on_retry(world, settings):
    world.seed_item("i1", "t1", b"img-a", phash="0000000000000000", vector=[1.0, 0.0])
    world.downloader.raise_transient = True
    runner, requeued, dlq = _runner(world, settings)
    assert runner.handle(_job("i1")).action == "retry"

    # storage recovers; the requeued job now succeeds
    world.downloader.raise_transient = False
    assert runner.handle(requeued[-1]).action == "done"
    assert world.items.items["i1"].status == "indexed"
