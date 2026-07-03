"""Ports the processor depends on. Concrete implementations live in
adapters.py; tests inject fakes. Keeping the processor free of SQLAlchemy /
boto3 / httpx is what makes the dedup-and-index logic unit-testable without
any running infrastructure.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


class TransientError(Exception):
    """A failure that may succeed on retry (storage/ai-service/db hiccup)."""


class PermanentError(Exception):
    """A failure that will never succeed (e.g. undecodable image). Dead-letter
    immediately rather than wasting retries."""


@dataclass
class ItemView:
    id: str
    tenant_id: str
    object_key: str
    content_type: str
    metadata: dict
    external_id: str | None
    status: str


class ItemStore(ABC):
    @abstractmethod
    def get(self, item_id: str) -> ItemView | None: ...

    @abstractmethod
    def mark_processing(self, item_id: str) -> None: ...

    @abstractmethod
    def mark_indexed(
        self, item_id: str, phash: str, collection: str, vector_id: str, model_version: str
    ) -> None: ...

    @abstractmethod
    def mark_duplicate(self, item_id: str, phash: str, duplicate_of_id: str) -> None: ...

    @abstractmethod
    def mark_failed(self, item_id: str, reason: str) -> None: ...

    @abstractmethod
    def list_indexed_phashes(self, tenant_id: str) -> list[tuple[str, str]]:
        """(item_id, phash) for the tenant's already-indexed items, for
        near-duplicate comparison."""


class ObjectDownloader(ABC):
    @abstractmethod
    def download(self, object_key: str) -> bytes:
        """Raise TransientError if storage is unreachable, PermanentError if
        the object is missing."""


class EmbedderClient(ABC):
    @abstractmethod
    def embed_image(self, image_bytes: bytes) -> tuple[list[float], str, str]:
        """Return (vector, phash, model_version). Raise TransientError if
        ai-service is unreachable, PermanentError if it rejects the image."""


class IndexVersionBumper(ABC):
    @abstractmethod
    def bump(self, tenant_id: str) -> None:
        """Advance the tenant's index version so query-service caches for that
        tenant are invalidated (Milestone 8). Best-effort."""
