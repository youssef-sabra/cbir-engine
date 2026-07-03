"""Application-level errors, translated to HTTP by the controllers layer."""

from __future__ import annotations


class ItemNotFoundError(Exception):
    pass


class DuplicateExternalIdError(Exception):
    pass


class UploadNotConfirmableError(Exception):
    """Confirmation requested but no object exists at the item's key yet."""


class UnsupportedContentTypeError(Exception):
    pass


class ObjectStorageError(Exception):
    """Object storage failed in a way the caller should retry."""
