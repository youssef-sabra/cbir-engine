"""Tests for the in-memory vector store (the Qdrant path is covered by the
live e2e). Verifies the search/filter/delete contract both implementations
must honour."""

from __future__ import annotations

from cbir_common.vectordb import InMemoryVectorStore, VectorRecord, collection_name


def test_collection_name_is_hex_and_tenant_scoped():
    name = collection_name("11111111-2222-3333-4444-555555555555")
    assert name == "tenant_11111111222233334444555555555555"


def _store():
    store = InMemoryVectorStore()
    store.ensure_collection("t1", dim=3)
    store.upsert(
        "t1",
        [
            VectorRecord("a", [1.0, 0.0, 0.0], {"category": "shoes"}),
            VectorRecord("b", [0.9, 0.1, 0.0], {"category": "shoes"}),
            VectorRecord("c", [0.0, 1.0, 0.0], {"category": "bags"}),
        ],
    )
    return store


def test_search_ranks_by_cosine_similarity():
    hits = _store().search("t1", [1.0, 0.0, 0.0], limit=3)
    assert [h.id for h in hits] == ["a", "b", "c"]
    assert hits[0].score >= hits[1].score >= hits[2].score


def test_metadata_filter_constrains_results():
    hits = _store().search("t1", [1.0, 0.0, 0.0], limit=10, filters={"category": "bags"})
    assert [h.id for h in hits] == ["c"]


def test_limit_truncates():
    assert len(_store().search("t1", [1.0, 0.0, 0.0], limit=2)) == 2


def test_delete_removes_points():
    store = _store()
    store.delete("t1", ["a"])
    assert store.count("t1") == 2
    assert all(h.id != "a" for h in store.search("t1", [1.0, 0.0, 0.0], limit=10))


def test_tenant_collections_are_isolated():
    store = _store()
    store.ensure_collection("t2", dim=3)
    assert store.count("t2") == 0
    assert store.count("t1") == 3
