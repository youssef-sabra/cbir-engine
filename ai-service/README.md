# ai-service

Embedding generation and reranking (Milestones 5 & 9). Turns images and text into vectors in a shared
space, and reranks candidate shortlists. Called internally by the ingestion worker (batch embedding at
index time) and by query-service (single embedding at query time, plus reranking). Per-tenant fine-tuning
(FR3) is a later milestone.

## Endpoints (internal — no tenant auth; network-isolated like a model sidecar)

| Method & path | Purpose |
|---|---|
| `POST /internal/embed` | Batch-embed a mixed list of image/text inputs; optional perceptual hash per image |
| `POST /internal/rerank` | Re-score a candidate shortlist against a query vector, with an optional compositional modifier |
| `GET /health`, `GET /readyz` | Liveness / readiness (reports the active provider + model version) |

Images cross the wire base64-encoded in JSON. `/internal/embed` returns each vector plus the
`model_version` tag that is stored alongside every indexed vector for provenance and re-indexing.

## The pluggable encoder (NFR16)

`EMBEDDING_PROVIDER` selects the encoder behind the `EmbeddingProviderPort`:

- **`local`** (default) — `LocalDeterministicEmbedder`: a CPU-only, dependency-light (Pillow + numpy)
  encoder producing a 512-dim vector from a grayscale thumbnail (structure) + RGB thumbnail (color) +
  luminance histogram (tone), L2-normalized. It gives **genuine image-to-image similarity** — visually
  similar images land near each other — so the whole retrieval pipeline runs and is testable locally with
  no GPU or model download. Text embeddings share the space dimensionally via a hashed bag-of-tokens but
  are **not** semantically aligned with images (that needs a learned model).
- **`siglip2` / `dinov2`** — adapters for the real encoders named in the architecture. They are honest
  stubs: loading them needs torch + GPU + multi-GB weights, so they raise a clear error until provisioned.
  Enabling one is a self-contained change to `infrastructure/embedding/model_adapters.py`.

> **Why a local default?** This is a local-first project with credential-free CI (Milestone 1). Real
> encoders can't be pulled here, and the PRD explicitly requires the encoder to be swappable. Building
> against the port with a deterministic default keeps the pipeline real, runnable, and green, and reduces
> "use SigLIP 2" to a one-file swap.

## Reranking (NFR17)

`CosineBlendReranker` scores candidates by cosine similarity to the query, optionally blending a
compositional modifier vector: `score = (1-w)·cos(query, cand) + w·cos(modifier, cand)`. This is the
pluggable rerank stage; a cross-encoder or MLLM reranker implements the same `RerankerPort`.

## Development

```
pip install -r requirements-dev.txt   # from this directory
ruff format --check . && ruff check .
python -m pytest -q
```

Stateless service — no database, no migrations. Unit tests need no external services.
