"""Typed representations of API responses — the SDK's stable vocabulary,
decoupled from raw JSON shapes (mirrors the backend DTO principle)."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CatalogItem:
    id: str
    status: str
    content_type: str
    metadata: dict = field(default_factory=dict)
    external_id: str | None = None
    size_bytes: int | None = None

    @classmethod
    def from_api(cls, data: dict) -> CatalogItem:
        return cls(
            id=data["id"],
            status=data["status"],
            content_type=data["content_type"],
            metadata=data.get("metadata", {}),
            external_id=data.get("external_id"),
            size_bytes=data.get("size_bytes"),
        )


@dataclass
class SearchResult:
    item_id: str
    score: float
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_api(cls, data: dict) -> SearchResult:
        return cls(
            item_id=data["item_id"],
            score=data["score"],
            metadata=data.get("metadata", {}),
        )
