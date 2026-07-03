"""Real Computer-Vision encoders behind the EmbeddingProviderPort (NFR16).

- `SigLIP2Embedder`  — the recommended production encoder. A jointly-trained
  vision-language model with a SHARED image/text embedding space, so the same
  vectors serve image-to-image, text-to-image, and compositional search.
  Multilingual. This is the platform's primary semantic model.
- `OpenClipEmbedder` — a fully-open alternative (ViT-B/32 … ViT-bigG/14, incl.
  DFN/SigLIP weights), same shared-space property.
- `DinoV2Embedder`  — a best-in-class *image-only* structural encoder for
  fine-grained similarity; it has no text tower, so `embed_texts` is rejected.

torch and the model libraries are imported lazily inside each class, so the
default `local` provider, the CI runner, and offline development never need
them installed. Weights are pulled from the Hugging Face hub on first load and
cached (mount a volume at HF_HOME in production to avoid re-downloading).

Embedding dimension is read from the loaded model, never hard-coded — the
ingestion worker sizes each tenant's vector collection from the actual vector
length, so switching encoders is a re-index (tracked by `model_version`), not
a schema change.
"""

from __future__ import annotations

import logging

import numpy as np

from ai_service.application.errors import InvalidImageError
from ai_service.application.ports import EmbeddingProviderPort
from ai_service.infrastructure.embedding.phash import (
    InvalidImageBytes,
    average_hash,
    open_image,
)

logger = logging.getLogger(__name__)


def _l2_normalize_rows(matrix: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0.0] = 1.0
    return matrix / norms


class _TorchEmbedder(EmbeddingProviderPort):
    """Shared machinery: lazy torch import, device selection, no-grad batched
    inference, L2 normalization, and the model-independent perceptual hash."""

    def __init__(self, checkpoint: str, device: str | None = None) -> None:
        import torch  # lazy: only when a real model is actually selected

        self._torch = torch
        self._checkpoint = checkpoint
        self._device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self._dim: int | None = None
        self._load()
        logger.info(
            "loaded encoder %s on %s (dim=%s)", checkpoint, self._device, self.embedding_dim
        )

    # subclasses implement the model-specific pieces
    def _load(self) -> None:  # pragma: no cover - requires weights
        raise NotImplementedError

    def _encode_images(self, images: list) -> np.ndarray:  # pragma: no cover
        raise NotImplementedError

    def _encode_texts(self, texts: list[str]) -> np.ndarray:  # pragma: no cover
        raise NotImplementedError

    @property
    def model_version(self) -> str:
        return f"{self._provider_name()}:{self._checkpoint}"

    @property
    def embedding_dim(self) -> int:
        return int(self._dim or 0)

    def _provider_name(self) -> str:  # pragma: no cover - trivial
        return "model"

    def embed_images(self, images: list[bytes]) -> list[list[float]]:
        if not images:
            return []
        pil = [self._open_rgb(b) for b in images]
        vectors = _l2_normalize_rows(self._encode_images(pil))
        return vectors.astype(np.float32).tolist()

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        vectors = _l2_normalize_rows(self._encode_texts(texts))
        return vectors.astype(np.float32).tolist()

    def perceptual_hash(self, image: bytes) -> str:
        try:
            return average_hash(image)
        except InvalidImageBytes as exc:
            raise InvalidImageError(str(exc)) from exc

    def _open_rgb(self, image: bytes):
        try:
            return open_image(image).convert("RGB")
        except InvalidImageBytes as exc:
            raise InvalidImageError(str(exc)) from exc

    def _to_numpy(self, features) -> np.ndarray:
        """Unwrap a features tensor from whatever transformers returned.

        Across transformers versions `get_image_features`/`get_text_features`
        may return a bare tensor or a model-output object; normalize both to a
        2-D numpy array of pooled feature vectors."""
        if not isinstance(features, self._torch.Tensor):
            if getattr(features, "pooler_output", None) is not None:
                features = features.pooler_output
            else:
                features = features.last_hidden_state[:, 0]
        return features.detach().cpu().numpy()


class SigLIP2Embedder(_TorchEmbedder):
    """SigLIP 2 via Hugging Face transformers (AutoModel + AutoProcessor).

    Default checkpoint is the base variant for a practical size/quality
    balance; set EMBEDDING_MODEL_CHECKPOINT to a larger SigLIP 2 (e.g.
    google/siglip2-so400m-patch14-384) for maximum retrieval quality.
    """

    DEFAULT_CHECKPOINT = "google/siglip2-base-patch16-224"

    def __init__(self, checkpoint: str | None = None, device: str | None = None) -> None:
        super().__init__(checkpoint or self.DEFAULT_CHECKPOINT, device)

    def _provider_name(self) -> str:
        return "siglip2"

    def _load(self) -> None:
        from transformers import AutoModel, AutoProcessor

        self._model = AutoModel.from_pretrained(self._checkpoint).to(self._device).eval()
        self._processor = AutoProcessor.from_pretrained(self._checkpoint)
        # Probe the true feature dimension from the model rather than assuming.
        self._dim = int(self._model.config.text_config.hidden_size)

    def _encode_images(self, images: list) -> np.ndarray:
        inputs = self._processor(images=images, return_tensors="pt").to(self._device)
        with self._torch.no_grad():
            features = self._model.get_image_features(**inputs)
        return self._to_numpy(features)

    def _encode_texts(self, texts: list[str]) -> np.ndarray:
        # SigLIP requires max-length padding for its text tower (unlike CLIP).
        inputs = self._processor(
            text=texts, return_tensors="pt", padding="max_length", truncation=True
        ).to(self._device)
        with self._torch.no_grad():
            features = self._model.get_text_features(**inputs)
        return self._to_numpy(features)


class OpenClipEmbedder(_TorchEmbedder):
    """OpenCLIP alternative. EMBEDDING_MODEL_CHECKPOINT selects the architecture
    (default ViT-B-32); EMBEDDING_MODEL_PRETRAINED selects the weights tag."""

    DEFAULT_CHECKPOINT = "ViT-B-32"
    DEFAULT_PRETRAINED = "laion2b_s34b_b79k"

    def __init__(
        self,
        checkpoint: str | None = None,
        device: str | None = None,
        pretrained: str | None = None,
    ) -> None:
        self._pretrained = pretrained or self.DEFAULT_PRETRAINED
        super().__init__(checkpoint or self.DEFAULT_CHECKPOINT, device)

    def _provider_name(self) -> str:
        return f"openclip:{self._pretrained}"

    def _load(self) -> None:
        import open_clip

        self._model, _, self._preprocess = open_clip.create_model_and_transforms(
            self._checkpoint, pretrained=self._pretrained, device=self._device
        )
        self._model.eval()
        self._tokenizer = open_clip.get_tokenizer(self._checkpoint)
        self._dim = int(self._model.text_projection.shape[1])

    def _encode_images(self, images: list) -> np.ndarray:
        batch = self._torch.stack([self._preprocess(img) for img in images]).to(self._device)
        with self._torch.no_grad():
            features = self._model.encode_image(batch)
        return self._to_numpy(features)

    def _encode_texts(self, texts: list[str]) -> np.ndarray:
        tokens = self._tokenizer(texts).to(self._device)
        with self._torch.no_grad():
            features = self._model.encode_text(tokens)
        return self._to_numpy(features)


class DinoV2Embedder(_TorchEmbedder):
    """DINOv2 — image-only structural encoder (no text tower)."""

    DEFAULT_CHECKPOINT = "facebook/dinov2-base"

    def __init__(self, checkpoint: str | None = None, device: str | None = None) -> None:
        super().__init__(checkpoint or self.DEFAULT_CHECKPOINT, device)

    def _provider_name(self) -> str:
        return "dinov2"

    def _load(self) -> None:
        from transformers import AutoImageProcessor, AutoModel

        self._model = AutoModel.from_pretrained(self._checkpoint).to(self._device).eval()
        self._processor = AutoImageProcessor.from_pretrained(self._checkpoint)
        self._dim = int(self._model.config.hidden_size)

    def _encode_images(self, images: list) -> np.ndarray:
        inputs = self._processor(images=images, return_tensors="pt").to(self._device)
        with self._torch.no_grad():
            outputs = self._model(**inputs)
        # CLS token is the pooled image representation.
        return outputs.last_hidden_state[:, 0, :].detach().cpu().numpy()

    def _encode_texts(self, texts: list[str]) -> np.ndarray:
        raise InvalidImageError(
            "dinov2 is an image-only encoder and cannot embed text; use siglip2 or "
            "openclip for text-to-image search"
        )
