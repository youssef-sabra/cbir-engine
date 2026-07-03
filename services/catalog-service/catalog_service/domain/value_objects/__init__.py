from __future__ import annotations

from enum import Enum


class ItemStatus(str, Enum):
    """Lifecycle of a catalog item, which doubles as its ingestion job status
    (FR1.4 async pipeline; the Milestone 4 acceptance criteria track exactly
    these states)."""

    # Metadata row exists; the tenant holds a signed upload URL but the bytes
    # haven't been confirmed in object storage yet.
    PENDING_UPLOAD = "pending_upload"
    # Bytes confirmed present in object storage and an ingestion job enqueued.
    QUEUED = "queued"
    # An ingestion worker has picked up the job (dedup -> embed -> index).
    PROCESSING = "processing"
    # Embedded and indexed into the vector store; searchable.
    INDEXED = "indexed"
    # A perceptual near-duplicate of an already-indexed item; not re-indexed
    # (FR1.2). `duplicate_of_id` points at the original.
    DUPLICATE = "duplicate"
    # Ingestion failed after retries; the job is in the dead-letter queue and
    # `failure_reason` explains why.
    FAILED = "failed"


# States from which a fresh ingestion job may be (re)queued.
QUEUEABLE_FROM = frozenset({ItemStatus.PENDING_UPLOAD, ItemStatus.FAILED})
