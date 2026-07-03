"""Search use cases: image-to-image, text-to-image, and composed
(image + text modifier). All share one execution core so caching, filtering,
pagination, and reranking behave identically across query types.

Pipeline: [cache lookup] -> embed query -> ANN search (with metadata filter)
-> [rerank] -> min-score filter -> pagination -> [cache store].

Reranking runs when a query is composed (always) or when the caller opts into
the "precise" mode; plain image/text search returns the ANN order directly
(the cosine reranker would not reorder it), keeping the fast path fast.
"""

from __future__ import annotations

import hashlib
import json

from query_service.application.dto import SearchResultsOutput
from query_service.application.ports import (
    IndexHit,
    QueryCachePort,
    QueryEmbedderPort,
    RerankerPort,
    SearchIndexPort,
)
from query_service.domain.value_objects import RankedResult, SearchParameters

# When reranking, over-fetch the ANN shortlist so the reranker has more than
# top_k candidates to reorder.
_RERANK_CANDIDATE_MULTIPLIER = 3
_RESULT_CACHE_TTL = 300
_EMBED_CACHE_TTL = 3600


class SearchService:
    def __init__(
        self,
        embedder: QueryEmbedderPort,
        index: SearchIndexPort,
        cache: QueryCachePort,
        reranker: RerankerPort | None = None,
    ) -> None:
        self._embedder = embedder
        self._index = index
        self._cache = cache
        self._reranker = reranker

    # -- public entry points --------------------------------------------------

    def by_image(
        self, tenant_id: str, image_bytes: bytes, params: SearchParameters, rerank: bool = False
    ) -> SearchResultsOutput:
        seed = "img:" + hashlib.sha256(image_bytes).hexdigest()
        return self._run(
            tenant_id, seed, lambda: self._cached_image_embed(image_bytes), params, rerank=rerank
        )

    def by_text(
        self, tenant_id: str, text: str, params: SearchParameters, rerank: bool = False
    ) -> SearchResultsOutput:
        seed = "txt:" + hashlib.sha256(text.encode("utf-8")).hexdigest()
        return self._run(
            tenant_id, seed, lambda: self._cached_text_embed(text), params, rerank=rerank
        )

    def composed(
        self, tenant_id: str, image_bytes: bytes, modifier_text: str, params: SearchParameters
    ) -> SearchResultsOutput:
        """Compositional query (Milestone 9): rank by the reference image but
        steer toward the text modifier via the reranker's modifier blend.
        Always reranks (that is what makes it compositional)."""
        seed = (
            "cmp:"
            + hashlib.sha256(image_bytes).hexdigest()
            + ":"
            + hashlib.sha256(modifier_text.encode("utf-8")).hexdigest()
        )
        modifier_vector = self._cached_text_embed(modifier_text)
        return self._run(
            tenant_id,
            seed,
            lambda: self._cached_image_embed(image_bytes),
            params,
            rerank=True,
            modifier_vector=modifier_vector,
        )

    # -- shared execution core ------------------------------------------------

    def _run(
        self,
        tenant_id: str,
        query_seed: str,
        embed,
        params: SearchParameters,
        rerank: bool,
        modifier_vector: list[float] | None = None,
    ) -> SearchResultsOutput:
        will_rerank = self._reranker is not None and (rerank or modifier_vector is not None)
        cache_key = self._result_key(tenant_id, query_seed, params, will_rerank)

        cached = self._cache.get_results(cache_key)
        if cached is not None:
            results = [RankedResult(**r) for r in cached]
            return SearchResultsOutput(results=results, cached=True, reranked=will_rerank)

        query_vector = embed()
        fetch = params.top_k + params.offset
        if will_rerank:
            fetch *= _RERANK_CANDIDATE_MULTIPLIER
        hits = self._index.search(
            tenant_id,
            query_vector,
            limit=fetch,
            filters=params.filters or None,
            with_vectors=will_rerank,
        )

        if will_rerank and hits:
            hits = self._apply_rerank(query_vector, modifier_vector, hits)

        ranked = [
            RankedResult(item_id=h.item_id, score=round(h.score, 6), payload=h.payload)
            for h in hits
            if h.score >= params.min_score
        ]
        page = ranked[params.offset : params.offset + params.top_k]

        self._cache.set_results(
            cache_key, [dict(r.__dict__) for r in page], ttl_seconds=_RESULT_CACHE_TTL
        )
        return SearchResultsOutput(results=page, cached=False, reranked=will_rerank)

    def _apply_rerank(
        self, query_vector: list[float], modifier_vector: list[float] | None, hits: list[IndexHit]
    ) -> list[IndexHit]:
        candidates = [(h.item_id, h.vector or []) for h in hits]
        order = self._reranker.rerank(query_vector, candidates, modifier_vector, top_k=len(hits))
        by_id = {h.item_id: h for h in hits}
        reordered = []
        for item_id, score in order:
            hit = by_id.get(item_id)
            if hit is not None:
                reordered.append(IndexHit(item_id=hit.item_id, score=score, payload=hit.payload))
        return reordered

    def _cached_image_embed(self, image_bytes: bytes) -> list[float]:
        key = "emb:img:" + hashlib.sha256(image_bytes).hexdigest()
        cached = self._cache.get_embedding(key)
        if cached is not None:
            return cached
        vector = self._embedder.embed_image(image_bytes)
        self._cache.set_embedding(key, vector, ttl_seconds=_EMBED_CACHE_TTL)
        return vector

    def _cached_text_embed(self, text: str) -> list[float]:
        key = "emb:txt:" + hashlib.sha256(text.encode("utf-8")).hexdigest()
        cached = self._cache.get_embedding(key)
        if cached is not None:
            return cached
        vector = self._embedder.embed_text(text)
        self._cache.set_embedding(key, vector, ttl_seconds=_EMBED_CACHE_TTL)
        return vector

    def _result_key(
        self, tenant_id: str, query_seed: str, params: SearchParameters, reranked: bool
    ) -> str:
        # The tenant's index version is part of the key: a re-index bumps the
        # version, so old keys are never read again (invalidation on reindex).
        version = self._cache.index_version(tenant_id)
        payload = json.dumps(
            {
                "t": tenant_id,
                "v": version,
                "seed": query_seed,
                "k": params.top_k,
                "o": params.offset,
                "m": params.min_score,
                "f": params.filters,
                "r": reranked,
            },
            sort_keys=True,
        )
        return "qs:results:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()
