"""cbir — the official Python SDK for the CBIR Engine (Milestone 11).

A thin, typed wrapper over the public REST API: authenticate with an API key,
ingest images (register → upload → confirm), and search by image / text /
composition. Deliberately minimal — the SDK adds convenience (auth header
attachment, the upload handshake, typed results) over an already
well-designed API, not business logic.

    from cbir import CBIRClient

    client = CBIRClient(api_key="cbir_...", catalog_url="http://localhost:8002",
                        query_url="http://localhost:8004")
    item = client.ingest_image("shoe.jpg", metadata={"category": "shoes"})
    results = client.search_by_image("query.jpg", top_k=5, filters={"category": "shoes"})
    for r in results:
        print(r.item_id, r.score)
"""

from cbir.client import CBIRClient
from cbir.errors import CBIRAPIError, CBIRAuthError
from cbir.models import CatalogItem, SearchResult

__all__ = [
    "CBIRClient",
    "CBIRAPIError",
    "CBIRAuthError",
    "CatalogItem",
    "SearchResult",
]

__version__ = "0.1.0"
