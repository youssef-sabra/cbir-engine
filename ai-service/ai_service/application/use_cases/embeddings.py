"""Embedding generation use case.

Groups a mixed batch by modality so each provider call is a single batched
inference (throughput), then reassembles results in the caller's original
order. Perceptual hashes are computed only for images and only when asked.
"""

from __future__ import annotations

from ai_service.application.dto import EmbedBatchOutput, EmbeddingResult, EmbedInput
from ai_service.application.errors import EmptyBatchError
from ai_service.application.ports import EmbeddingProviderPort
from ai_service.domain.value_objects import Modality


class GenerateEmbeddings:
    def __init__(self, provider: EmbeddingProviderPort) -> None:
        self._provider = provider

    def execute(self, inputs: list[EmbedInput], include_phash: bool = False) -> EmbedBatchOutput:
        if not inputs:
            raise EmptyBatchError("embed request contained no inputs")

        image_positions = [i for i, x in enumerate(inputs) if x.modality is Modality.IMAGE]
        text_positions = [i for i, x in enumerate(inputs) if x.modality is Modality.TEXT]

        image_vectors = (
            self._provider.embed_images([inputs[i].image_bytes or b"" for i in image_positions])
            if image_positions
            else []
        )
        text_vectors = (
            self._provider.embed_texts([inputs[i].text or "" for i in text_positions])
            if text_positions
            else []
        )

        results: list[EmbeddingResult | None] = [None] * len(inputs)
        for pos, vec in zip(image_positions, image_vectors, strict=False):
            phash = (
                self._provider.perceptual_hash(inputs[pos].image_bytes or b"")
                if include_phash
                else None
            )
            results[pos] = EmbeddingResult(vector=vec, phash=phash)
        for pos, vec in zip(text_positions, text_vectors, strict=False):
            results[pos] = EmbeddingResult(vector=vec, phash=None)

        return EmbedBatchOutput(
            model_version=self._provider.model_version,
            embedding_dim=self._provider.embedding_dim,
            results=[r for r in results if r is not None],
        )
