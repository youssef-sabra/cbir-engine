"""Application-level errors. Translated to HTTP responses by the controllers
layer — use cases themselves know nothing about status codes."""

from __future__ import annotations

from dataclasses import dataclass


class TenantNotFoundError(Exception):
    pass


class TenantNameConflictError(Exception):
    pass


class ApiKeyNotFoundError(Exception):
    pass


class AuthenticationError(Exception):
    """Credential rejected. The message is safe to return to the caller."""


@dataclass
class RateLimitExceededError(Exception):
    limit_per_minute: int
    retry_after_seconds: int

    def __str__(self) -> str:
        return (
            f"rate limit of {self.limit_per_minute} requests/minute exceeded; "
            f"retry in {self.retry_after_seconds}s"
        )
