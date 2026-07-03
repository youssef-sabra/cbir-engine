# AI Pipeline Audit & Encoder Upgrade

**Date:** 2026-07-03 — performed before starting Milestone 10.

---

## 1. Audit — what the embedding pipeline was

The active encoder was `LocalDeterministicEmbedder` (`EMBEDDING_PROVIDER=local`): a Pillow + numpy
function producing a 512-dim vector from a grayscale thumbnail (structure) + RGB thumbnail (color) +
luminance histogram (tone). It gives real image-to-image *visual* similarity, but:

- **no learned semantics** — it cannot tell "a running shoe" from "a loaf of bread" if they share color/layout;
- **no true cross-modal alignment** — text embeddings shared the vector space only *dimensionally* (a
  hashed bag-of-tokens), so text-to-image search (FR2.2) and compositional queries (FR2.3) were structural,
  not semantic.

The `siglip2`/`dinov2` providers were `NotImplementedError` stubs. So the semantic model was a placeholder.

## 2. Recommendation — SigLIP 2

Adopt **SigLIP 2** (`google/siglip2-*`) as the primary production encoder, with OpenCLIP as a first-class
alternative and DINOv2 as a secondary image-only structural encoder.

| Option | Shared image+text space | Notes |
|---|---|---|
| **SigLIP 2** | ✅ | SOTA zero-shot + retrieval, sigmoid loss, **multilingual**. Chosen. |
| OpenCLIP | ✅ | Fully open; ViT-B/32 … ViT-bigG/14 incl. DFN/SigLIP weights. Implemented as an alternative. |
| DINOv2 | ❌ image-only | Best-in-class fine-grained structural similarity; can't serve text-to-image alone. Secondary. |
| OpenAI CLIP | ✅ | Superseded by SigLIP 2 / DFN on retrieval. |

The platform's differentiators — text-to-image and compositional search — *require* a jointly-trained
shared embedding space, which SigLIP 2 leads while adding multilingual coverage (valuable for a
multi-tenant SaaS). DINOv2 is excellent but image-only, so it cannot be primary.

## 3. Implementation

All behind the existing `EmbeddingProviderPort` (NFR16 swappability) — no changes to the ingestion
worker, query-service, or vector store were needed:

- `ai_service/infrastructure/embedding/model_adapters.py` — real `SigLIP2Embedder` (transformers),
  `OpenClipEmbedder` (open-clip-torch), and image-only `DinoV2Embedder`. Shared `_TorchEmbedder` base:
  lazy torch import, device auto-detect (cuda/cpu), no-grad batched inference, L2-normalization, and a
  version-robust tensor unwrap. Embedding dimension is read from the loaded model.
- `phash.py` — the perceptual hash (dedup, FR1.2) factored into a shared module; it is model-independent,
  so dedup behaves identically under every encoder.
- Config (`EMBEDDING_PROVIDER`, `EMBEDDING_MODEL_CHECKPOINT`, `EMBEDDING_MODEL_PRETRAINED`,
  `EMBEDDING_DEVICE`), `requirements-ml.txt`, a Dockerfile `INSTALL_ML` build arg, and
  `docker-compose.siglip.yml` (builds the ML image, selects SigLIP 2, caches weights on a volume).

**Why `local` remains the default:** real weights are multi-gigabyte and cannot be pulled on the
credential-free CI runner (Milestone 1), and forcing every `docker compose up` to download them would
break the local-first "just works" property. `local` is therefore the CI/offline default; SigLIP 2 is the
documented, ready-to-run production encoder — one env var / one compose overlay away. Switching encoders
changes the embedding dimension, so existing catalogs must be re-indexed (the `model_version` stored with
every vector makes stale vectors identifiable).

## 4. Verification (against real weights)

`google/siglip2-base-patch16-224` was downloaded and run locally through the repo's `SigLIP2Embedder`:

- model loaded; embedding dim **768** (read from the model config, not hardcoded);
- image embeddings **L2-normalized**;
- **image-to-image** semantically ordered: near-identical reds cos **0.9987** vs red–blue **0.9382**;
- **text-to-image cross-modal alignment** works: "a solid red image" is closer to the red image
  (**0.158**) than to the blue image (**0.108**) — the capability the placeholder could not provide.

Committed gated tests (`tests/test_model_adapters.py`, run with `CBIR_RUN_ML_TESTS=1` + `requirements-ml`)
pass against the real model (6 passed). Running the model surfaced and fixed a real transformers-5.x issue
(`get_image_features` returning a wrapped output object rather than a bare tensor).

Regression: the default suite is unchanged — **112 unit tests pass, lint clean**; the 7 ML tests skip
without torch (so CI stays green and download-free).

## 5. Net effect

The semantic placeholder is replaced by a real, verified production CV model. Enable it with:

```
docker compose -f docker-compose.yml -f docker-compose.siglip.yml up --build
# or: EMBEDDING_PROVIDER=siglip2 with requirements-ml.txt installed
```
