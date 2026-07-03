"""Processor tests: the dedup-and-index decision (Milestone 4 acceptance
criteria at the unit level)."""

from __future__ import annotations

from ingestion_worker.dedup import find_duplicate, hamming_distance


class TestDedupMath:
    def test_hamming_distance(self):
        assert hamming_distance("0000000000000000", "0000000000000000") == 0
        assert hamming_distance("0000000000000000", "0000000000000001") == 1
        assert hamming_distance("00000000000000ff", "0000000000000000") == 8

    def test_find_duplicate_within_threshold(self):
        existing = [("a", "0000000000000000"), ("b", "00000000000000ff")]
        assert find_duplicate("0000000000000001", existing, threshold=5) == "a"
        assert find_duplicate("0f0f0f0f0f0f0f0f", existing, threshold=5) is None

    def test_find_duplicate_prefers_closest(self):
        existing = [("far", "0000000000000003"), ("near", "0000000000000001")]
        assert find_duplicate("0000000000000000", existing, threshold=5) == "near"


class TestProcess:
    def test_first_item_gets_indexed(self, world):
        world.seed_item("i1", "t1", b"img-a", phash="0000000000000000", vector=[1.0, 0.0])
        result = world.processor().process("i1")
        assert result.outcome == "indexed"
        assert world.items.items["i1"].status == "indexed"
        # vector present in the tenant's collection with a searchable payload
        assert world.vectors.count("t1") == 1
        hits = world.vectors.search("t1", [1.0, 0.0], limit=1)
        assert hits[0].id == "i1"
        assert hits[0].payload.get("category") == "shoes"
        # embedding_ref recorded + cache invalidation bumped
        assert world.items.embedding_refs and world.items.embedding_refs[0][0] == "i1"
        assert world.bumper.bumped == ["t1"]

    def test_near_duplicate_is_not_reindexed(self, world):
        world.seed_item("i1", "t1", b"img-a", phash="0000000000000000", vector=[1.0, 0.0])
        world.processor().process("i1")
        # second, near-identical image (1 bit different) for the same tenant
        world.seed_item("i2", "t1", b"img-b", phash="0000000000000001", vector=[1.0, 0.0])
        result = world.processor().process("i2")
        assert result.outcome == "duplicate"
        assert result.duplicate_of == "i1"
        assert world.items.items["i2"].status == "duplicate"
        # not added to the vector store (no redundant indexing)
        assert world.vectors.count("t1") == 1

    def test_dissimilar_image_indexed_separately(self, world):
        world.seed_item("i1", "t1", b"img-a", phash="0000000000000000", vector=[1.0, 0.0])
        world.processor().process("i1")
        world.seed_item("i2", "t1", b"img-c", phash="ffffffffffffffff", vector=[0.0, 1.0])
        assert world.processor().process("i2").outcome == "indexed"
        assert world.vectors.count("t1") == 2

    def test_same_phash_different_tenant_is_not_duplicate(self, world):
        world.seed_item("i1", "t1", b"img-a", phash="0000000000000000", vector=[1.0, 0.0])
        world.processor().process("i1")
        # identical hash, different tenant -> indexed, isolation preserved
        world.seed_item("i2", "t2", b"img-a2", phash="0000000000000000", vector=[1.0, 0.0])
        assert world.processor().process("i2").outcome == "indexed"
        assert world.vectors.count("t2") == 1

    def test_redelivered_indexed_job_is_noop(self, world):
        world.seed_item("i1", "t1", b"img-a", phash="0000000000000000", vector=[1.0, 0.0])
        world.processor().process("i1")
        # simulate at-least-once redelivery
        assert world.processor().process("i1").outcome == "skipped"
        assert world.vectors.count("t1") == 1

    def test_missing_item_is_skipped(self, world):
        assert world.processor().process("ghost").outcome == "skipped"
