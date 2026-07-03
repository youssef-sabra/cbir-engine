"""Minimal cross-service domain kernel.

Only concepts that are genuinely universal across more than one service's
domain layer belong here, and only when duplicating them would create a
correctness risk (two services disagreeing on what a valid TenantId looks
like). See docs/CLEAN_ARCHITECTURE.md Section 5. Resist growing this package.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass


class InvalidTenantIdError(ValueError):
    """Raised when a raw value cannot be parsed as a TenantId."""


@dataclass(frozen=True)
class TenantId:
    """Identity of a tenant, shared vocabulary across every service.

    A UUID wrapper rather than a bare string/UUID so that the type system —
    not naming conventions — distinguishes tenant identity from every other
    id flowing through the platform.
    """

    value: uuid.UUID

    @classmethod
    def new(cls) -> TenantId:
        return cls(uuid.uuid4())

    @classmethod
    def parse(cls, raw: object) -> TenantId:
        if isinstance(raw, TenantId):
            return raw
        if isinstance(raw, uuid.UUID):
            return cls(raw)
        try:
            return cls(uuid.UUID(str(raw)))
        except (ValueError, AttributeError, TypeError) as exc:
            raise InvalidTenantIdError(f"not a valid tenant id: {raw!r}") from exc

    def __str__(self) -> str:
        return str(self.value)
