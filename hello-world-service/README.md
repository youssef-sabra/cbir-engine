# hello-world-service

**This service is temporary.**

Its only purpose is to prove that the full pipeline — build, lint, test, containerize, join the Docker
Compose network, and respond to health checks — works end to end, before any real business logic exists.

It does **not** follow the Clean Architecture layering used by the real services introduced from
Milestone 2 onward (`domain/`, `application/`, `interface_adapters/`, `infrastructure/`) — that structure
isn't earned yet by a service with no business logic to layer. It is deliberately a single flat `app/`
module.

## Endpoints

- `GET /health` — liveness check. Returns 200 with service name/version if the process is running.
- `GET /readyz` — readiness check. Additionally verifies TCP connectivity to Postgres, Redis, Qdrant, and
  MinIO over the Compose network — proving the whole local stack is wired together correctly, not just this
  one container.

## Removal

This directory, its Compose service entry, and its CI job will be deleted once Milestone 2's
`services/auth-service` exists and is deployable in its place.
