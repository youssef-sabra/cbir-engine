from __future__ import annotations

from dataclasses import dataclass

from ai_service.application.use_cases.embeddings import GenerateEmbeddings
from ai_service.application.use_cases.reranking import RerankShortlist


@dataclass(frozen=True)
class UseCaseBundle:
    generate_embeddings: GenerateEmbeddings
    rerank_shortlist: RerankShortlist
