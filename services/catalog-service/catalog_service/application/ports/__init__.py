"""Ports the catalog use cases need beyond repositories."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class PresignedUpload:
    url: str
    method: str
    headers: dict
    expires_in_seconds: int


@dataclass(frozen=True)
class ObjectStat:
    size_bytes: int


class ObjectStoragePort(ABC):
    """What the domain needs from object storage, expressed without S3
    vocabulary leaking inward. The S3 adapter lives in infrastructure/ and
    works identically against MinIO locally and GCS/S3/Azure (S3 API) in
    production — the Milestone 1 open-protocol principle."""

    @abstractmethod
    def ensure_bucket(self) -> None: ...

    @abstractmethod
    def presign_upload(
        self, object_key: str, content_type: str, expires_in_seconds: int
    ) -> PresignedUpload: ...

    @abstractmethod
    def presign_download(self, object_key: str, expires_in_seconds: int) -> str: ...

    @abstractmethod
    def stat_object(self, object_key: str) -> ObjectStat | None: ...

    @abstractmethod
    def delete_object(self, object_key: str) -> None:
        """Idempotent: deleting a missing object is not an error."""


@dataclass(frozen=True)
class IngestionJob:
    tenant_id: str
    item_id: str
    object_key: str


class IngestionQueuePort(ABC):
    """Hands a confirmed item to the asynchronous ingestion pipeline. The
    concrete implementation is a Redis queue producer; the consumer is the
    ingestion-worker. Decouples upload-response latency from embedding work
    (FR1.4) — the upload/confirm call returns immediately with the item in
    QUEUED state."""

    @abstractmethod
    def enqueue(self, job: IngestionJob) -> None: ...

    @abstractmethod
    def reachable(self) -> bool: ...


class Clock(ABC):
    @abstractmethod
    def now(self) -> datetime: ...


class SystemClock(Clock):
    def now(self) -> datetime:
        return datetime.now(timezone.utc)
