from __future__ import annotations

from dataclasses import dataclass

from query_service.application.use_cases.search import SearchService


@dataclass(frozen=True)
class UseCaseBundle:
    search: SearchService
