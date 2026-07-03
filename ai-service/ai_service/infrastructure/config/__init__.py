"""Environment configuration — the only place environment variables are read."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    service_name: str = "ai-service"
    service_version: str = "0.1.0"

    # Which encoder to load, behind the EmbeddingProviderPort:
    #   local    -> deterministic CPU embedder (no torch / no download); CI + offline default
    #   siglip2  -> SigLIP 2 (recommended production encoder; shared image/text space)
    #   openclip -> OpenCLIP alternative
    #   dinov2   -> image-only structural encoder
    # The real models need the ML dependencies (see ai-service/requirements-ml.txt)
    # and download weights from the Hugging Face hub on first load.
    embedding_provider: str = "local"

    # Optional overrides for the real encoders. Empty -> the provider's
    # recommended default checkpoint.
    embedding_model_checkpoint: str = ""
    embedding_model_pretrained: str = ""  # OpenCLIP weights tag only
    embedding_device: str = ""  # e.g. "cuda" / "cpu"; empty -> auto-detect

    # Blend weight for the compositional modifier in the default reranker.
    rerank_modifier_weight: float = 0.5
