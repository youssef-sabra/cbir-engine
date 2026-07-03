from __future__ import annotations


class CBIRError(Exception):
    """Base class for all SDK errors."""


class CBIRAuthError(CBIRError):
    """The API key was rejected (401) or lacked a required scope (403)."""


class CBIRAPIError(CBIRError):
    """The API returned an error. `status_code` and `detail` carry the API's
    own, actionable message (NFR21)."""

    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(f"API error {status_code}: {detail}")
        self.status_code = status_code
        self.detail = detail
