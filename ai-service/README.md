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

- **`siglip2`** — **the recommended production encoder** (`SigLIP2Embedder`, transformers). SigLIP 2 is a
  jointly-trained vision-language model with a **shared image/text embedding space**, so the same vectors
  serve image-to-image, text-to-image, and compositional search; it is multilingual and currently leads
  zero-shot retrieval. Default checkpoint `google/siglip2-base-patch16-224`; set
  `EMBEDDING_MODEL_CHECKPOINT=google/siglip2-so400m-patch14-384` for maximum quality. Embedding dimension
  is read from the loaded model (base = 768).
- **`openclip`** — a fully-open alternative (`OpenClipEmbedder`, open-clip-torch): ViT-B/32 … ViT-bigG/14,
  incl. DFN/SigLIP weights (`EMBEDDING_MODEL_CHECKPOINT` + `EMBEDDING_MODEL_PRETRAINED`). Same shared-space
  property.
- **`dinov2`** — a best-in-class **image-only** structural encoder (`DinoV2Embedder`, transformers) for
  fine-grained similarity. It has no text tower, so `embed_texts` is rejected — use `siglip2`/`openclip`
  for text-to-image.
- **`local`** (default) — `LocalDeterministicEmbedder`: a CPU-only, dependency-light (Pillow + numpy)
  encoder producing a 512-dim vector from a grayscale thumbnail (structure) + RGB thumbnail (color) +
  luminance histogram (tone), L2-normalized. Genuine image-to-image *visual* similarity with no learned
  semantics and no true cross-modal alignment. It exists as the **offline / CI fallback** — not the
  quality path.

The real encoders need the ML dependencies (`requirements-ml.txt`: torch, transformers, open-clip) and
download weights from the Hugging Face hub on first load (cache `HF_HOME` on a volume in production).

### Running the real encoder

```
# locally, with the SigLIP 2 overlay (builds the ML image, downloads weights once):
docker compose -f docker-compose.yml -f docker-compose.siglip.yml up --build

# or in a Python env:
pip install -r requirements.txt -r requirements-ml.txt
EMBEDDING_PROVIDER=siglip2 uvicorn ai_service.main:app
```

> **Why is `local` still the default?** Real weights are multi-gigabyte and can't be pulled on the
> credential-free CI runner (Milestone 1), and forcing every `docker compose up` to download them would
> break the local-first "just works" property. So `local` is the default for CI/offline, and SigLIP 2 is
> the documented, ready-to-run production encoder — one env var away, behind the same
> `EmbeddingProviderPort`. Switching encoders changes the embedding dimension, so existing catalogs must be
> re-indexed (the `model_version` stored with every vector makes stale vectors identifiable).

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
