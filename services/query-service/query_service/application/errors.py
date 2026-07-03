from __future__ import annotations


class EmbeddingServiceError(Exception):
    """The embedding service could not be reached or rejected the query."""


class InvalidQueryError(Exception):
    """The query payload itself is invalid (e.g. an undecodable image)."""
