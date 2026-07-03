"""Gateway-style request authentication for resource services.

The production architecture validates credentials and enforces rate limits
at the API Gateway before requests reach backend services. No gateway exists
in the local-first stack yet, so resource services delegate that exact
responsibility to auth-service's /internal/validate endpoint through this
dependency. When a real gateway is introduced, it takes over this call and
resource services keep trusting the same TenantContext contract.
"""

from __future__ import annotations

from collections.abc import Callable

import httpx
from fastapi import HTTPException, Request

from cbir_common.auth.context import TenantContext


class AuthServiceClient:
    """Thin client for auth-service's internal validation endpoint."""

    def __init__(self, base_url: str, timeout_seconds: float = 5.0) -> None:
        self._client = httpx.Client(base_url=base_url, timeout=timeout_seconds)

    def health_reachable(self) -> bool:
        try:
            return self._client.get("/health").status_code == 200
        except httpx.HTTPError:
            return False

    def validate_request_credentials(
        self, api_key: str | None, authorization: str | None
    ) -> TenantContext:
        """Validate credentials, translating auth-service's verdict into the
        equivalent HTTPException so resource services return identical
        status codes/headers to what a gateway would have returned."""
        headers = {}
        if api_key:
            headers["X-API-Key"] = api_key
        if authorization:
            headers["Authorization"] = authorization
        if not headers:
            raise HTTPException(
                status_code=401,
                detail="missing credentials: provide X-API-Key or Authorization: Bearer",
                headers={"WWW-Authenticate": "Bearer"},
            )
        try:
            response = self._client.post("/internal/validate", headers=headers)
        except httpx.HTTPError as exc:
            raise HTTPException(
                status_code=503, detail="authentication service unavailable"
            ) from exc

        if response.status_code == 200:
            return TenantContext(**response.json())
        if response.status_code in (401, 429):
            try:
                detail = response.json().get("detail", "unauthorized")
            except ValueError:
                detail = "unauthorized"
            passthrough_headers = {}
            if response.headers.get("Retry-After"):
                passthrough_headers["Retry-After"] = response.headers["Retry-After"]
            if response.status_code == 401:
                passthrough_headers["WWW-Authenticate"] = "Bearer"
            raise HTTPException(
                status_code=response.status_code,
                detail=detail,
                headers=passthrough_headers or None,
            )
        raise HTTPException(
            status_code=503, detail="authentication service returned an unexpected response"
        )


def build_scope_dependency(
    client: AuthServiceClient, required_scope: str
) -> Callable[[Request], TenantContext]:
    """Build a FastAPI dependency enforcing authentication plus one scope.

    Scope enforcement happens here (in the resource service) rather than in
    auth-service, because which scope an endpoint requires is knowledge that
    belongs to the resource owning the endpoint.
    """

    def dependency(request: Request) -> TenantContext:
        context = client.validate_request_credentials(
            api_key=request.headers.get("X-API-Key"),
            authorization=request.headers.get("Authorization"),
        )
        if not context.has_scope(required_scope):
            raise HTTPException(
                status_code=403,
                detail=f"credential lacks required scope '{required_scope}'",
            )
        return context

    return dependency
