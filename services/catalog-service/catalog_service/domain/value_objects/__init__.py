from __future__ import annotations

from enum import Enum


class ItemStatus(str, Enum):
    # Metadata row exists; the tenant holds a signed upload URL but the bytes
    # haven't been confirmed in object storage yet.
    PENDING_UPLOAD = "pending_upload"
    # Bytes confirmed present in object storage; ready for the Milestone 4+
    # pipeline (dedup -> embed -> index).
    UPLOADED = "uploaded"
