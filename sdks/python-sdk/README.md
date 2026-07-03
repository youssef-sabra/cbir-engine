# cbir — Python SDK

The official Python client for the CBIR Engine. A thin, typed wrapper over the public REST API.

## Install

```
pip install -e sdks/python-sdk      # from the repo; a published package would be `pip install cbir`
```

## Quickstart

```python
from cbir import CBIRClient

client = CBIRClient(
    api_key="cbir_...",                      # from `python scripts/provision_tenant.py`
    catalog_url="http://localhost:8002",
    query_url="http://localhost:8004",
)

# Ingest (register -> upload -> confirm, in one call)
item = client.ingest_image("shoe.jpg", metadata={"category": "shoes"})

# Poll until searchable
while client.get_item(item.id).status not in ("indexed", "duplicate", "failed"):
    ...

# Search
for r in client.search_by_text("red running shoes", top_k=5, filters={"category": "shoes"}):
    print(r.item_id, r.score)

for r in client.search_by_image("query.jpg", top_k=5):
    print(r.item_id, r.score)

# Compositional ("like this, but in blue")
client.search_composed("shoe.jpg", modifier="in blue", top_k=5)

# Feedback
client.submit_feedback(item.id, query_ref="red running shoes", relevant=True)
```

## API

| Method | Purpose |
|---|---|
| `ingest_image(path, metadata=, external_id=)` | Register + upload + confirm |
| `get_item(id)` / `list_items(status=, limit=)` | Read catalog items / poll status |
| `delete_item(id)` | Right-to-erasure delete |
| `search_by_image(path, top_k=, filters=)` | Image-to-image search |
| `search_by_text(query, top_k=, filters=)` | Text-to-image search |
| `search_composed(path, modifier, top_k=, filters=)` | Compositional search |
| `submit_feedback(id, query_ref, relevant)` | Relevance feedback |

Errors are typed: `CBIRAuthError` (401/403) and `CBIRAPIError` (carries the API's status + `detail`).

## Tests

```
pip install -r requirements-dev.txt
python -m pytest -q         # uses httpx MockTransport — no live stack required
```
