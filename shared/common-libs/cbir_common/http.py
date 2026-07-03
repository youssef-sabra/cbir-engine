"""Small shared HTTP helpers for the FastAPI services."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

# Baseline security response headers (Milestone 12 hardening). These are the
# API-appropriate subset; a browser SPA would add a CSP at the CDN/edge.
_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "no-store",
}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        for name, value in _SECURITY_HEADERS.items():
            response.headers.setdefault(name, value)
        return response


def add_security_headers(app: FastAPI) -> None:
    app.add_middleware(SecurityHeadersMiddleware)


def configure_cors(app: FastAPI, allow_origins: str) -> None:
    """Enable CORS so the browser dashboard (a separate origin) can call the
    public API. `allow_origins` is a comma-separated list, or "*" for local
    development. In production set it to the dashboard's exact origin(s)."""
    if not allow_origins:
        return
    origins = ["*"] if allow_origins.strip() == "*" else [
        o.strip() for o in allow_origins.split(",") if o.strip()
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
