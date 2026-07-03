from __future__ import annotations

from pydantic import BaseModel


class TenantContext(BaseModel):
    """The authenticated identity attached to a request after validation.

    This is the contract between auth-service (which produces it) and every
    resource service (which consumes it). It deliberately carries only what
    resource services need for authorization and data isolation.
    """

    tenant_id: str
    api_key_id: str
    scopes: list[str]
    plan_tier: str

    def has_scope(self, scope: str) -> bool:
        return scope in self.scopes
