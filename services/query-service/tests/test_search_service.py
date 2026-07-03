"""Unit tests for the search execution core: ranking, filtering, pagination,
caching + invalidation (M8), and compositional rerank (M9)."""

from __future__ import annotations

from query_service.domain.value_objects import SearchParameters
from tests.conftest import World


def _params(top_k=10, offset=0, min_score=0.0, filters=None):
    return SearchParameters(top_k=top_k, offset=offset, min_score=min_score, filters=filters or {})


class TestRankingAndFilter:
    def test_query_returns_nearest_first_with_scores(self, world: World):
        t = "t1"
        world.embedder.images[b"query"] = [1.0, 0.0, 0.0]
        world.index_item(t, "near", [0.9, 0.1, 0.0], {"category": "shoes"})
        world.index_item(t, "far", [0.0, 1.0, 0.0], {"category": "bags"})
        out = world.service().by_image(t, b"query", _params())
        assert [r.item_id for r in out.results] == ["near", "far"]
        assert out.results[0].score >= out.results[1].score

    def test_metadata_filter_constrains_results(self, world: World):
        t = "t1"
        world.embedder.images[b"q"] = [1.0, 0.0, 0.0]
        world.index_item(t, "a", [1.0, 0.0, 0.0], {"category": "shoes"})
        world.index_item(t, "b", [1.0, 0.0, 0.0], {"category": "bags"})
        out = world.service().by_image(t, b"q", _params(filters={"category": "bags"}))
        assert [r.item_id for r in out.results] == ["b"]

    def test_min_score_threshold_excludes_low_similarity(self, world: World):
        t = "t1"
        world.embedder.images[b"q"] = [1.0, 0.0, 0.0]
        world.index_item(t, "match", [1.0, 0.0, 0.0])
        world.index_item(t, "orthogonal", [0.0, 1.0, 0.0])
        out = world.service().by_image(t, b"q", _params(min_score=0.5))
        assert [r.item_id for r in out.results] == ["match"]

    def test_pagination(self, world: World):
        t = "t1"
        world.embedder.images[b"q"] = [1.0, 0.0, 0.0]
        for i in range(5):
            world.index_item(t, f"i{i}", [1.0, 0.0, i * 0.01])
        first = world.service().by_image(t, b"q", _params(top_k=2, offset=0))
        second = world.service().by_image(t, b"q", _params(top_k=2, offset=2))
        assert len(first.results) == 2 and len(second.results) == 2
        assert {r.item_id for r in first.results}.isdisjoint({r.item_id for r in second.results})

    def test_text_query_path(self, world: World):
        t = "t1"
        world.embedder.texts["red shoes"] = [1.0, 0.0, 0.0]
        world.index_item(t, "a", [1.0, 0.0, 0.0])
        out = world.service().by_text(t, "red shoes", _params())
        assert out.results[0].item_id == "a"


class TestCaching:
    def _cached_world(self):
        w = World()
        w.embedder.images[b"q"] = [1.0, 0.0, 0.0]
        w.index_item("t1", "a", [1.0, 0.0, 0.0])
        return w

    def test_repeat_query_served_from_cache_without_reembedding(self):
        w = self._cached_world()
        svc = w.service()
        first = svc.by_image("t1", b"q", _params())
        assert first.cached is False
        searches_after_first = w.index.searches
        second = svc.by_image("t1", b"q", _params())
        assert second.cached is True
        # No new embed or index search on the cache hit.
        assert w.index.searches == searches_after_first
        assert [r.item_id for r in second.results] == [r.item_id for r in first.results]

    def test_reindex_invalidates_cache(self):
        w = self._cached_world()
        svc = w.service()
        svc.by_image("t1", b"q", _params())  # populate cache
        # A new item is indexed and the tenant's index version bumps.
        w.index_item("t1", "b", [0.99, 0.0, 0.0])
        w.cache.bump("t1")
        out = svc.by_image("t1", b"q", _params())
        assert out.cached is False  # old key unreachable -> recomputed
        assert "b" in {r.item_id for r in out.results}


class TestCompositionalRerank:
    def test_modifier_steers_results(self, world: World):
        t = "t1"
        world.embedder.images[b"ref"] = [1.0, 0.0, 0.0]  # "red" reference
        world.embedder.texts["in blue"] = [0.0, 0.0, 1.0]  # "blue" modifier
        world.index_item(t, "red", [1.0, 0.0, 0.0])
        # A blue-ish item that still shares some structure with the red query;
        # the 0.5/0.5 blend of image + modifier similarity lifts it past pure
        # red (0.5*0.5 + 0.5*0.87 = 0.685 > 0.5).
        world.index_item(t, "blue", [0.5, 0.0, 0.87])
        out = world.service().composed(t, b"ref", "in blue", _params())
        assert out.reranked is True
        assert out.results[0].item_id == "blue"

    def test_plain_search_not_reranked_by_default(self, world: World):
        world.embedder.images[b"q"] = [1.0, 0.0, 0.0]
        world.index_item("t1", "a", [1.0, 0.0, 0.0])
        out = world.service().by_image("t1", b"q", _params())
        assert out.reranked is False
