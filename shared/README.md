# shared/

Minimal cross-service code, deliberately kept small — see `docs/CLEAN_ARCHITECTURE.md` Section 5 for why
over-sharing is treated as a design smell.

## Packages

- **`domain-kernel/`** (`cbir_domain_kernel`) — genuinely universal domain concepts referenced by more
  than one service's domain layer. Currently: `TenantId`. Something belongs here only if duplicating it
  would create a correctness risk, not merely to avoid retyping a class.
- **`common-libs/`** (`cbir_common`) — cross-cutting technical utilities with no business meaning:
  - `structured_logging` — identical JSON log shape across services.
  - `auth.jwt_contract` — the platform access-token claim contract (signer: auth-service; verifiers:
    everyone else). Single source of truth so signer and verifiers cannot drift.
  - `auth.fastapi_dependency` — gateway-style request authentication: resource services delegate
    credential validation, revocation, and rate limiting to auth-service's `/internal/validate`
    endpoint, which plays the API-gateway role until a real gateway exists.

## Installing

Services consume these as normal installable packages:

- Locally/tests: each service's `requirements-dev.txt` installs them editable (`-e ../../shared/...`).
- Docker: each service's Dockerfile builds from the repository root context and `pip install`s them.
