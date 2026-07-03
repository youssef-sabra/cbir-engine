# CBIR Engine

A production-quality Content-Based Image Retrieval (CBIR) SaaS platform, built as a portfolio project
following Clean Architecture, with a **local-first development environment** and a **cloud-agnostic
infrastructure design** (reference production target: Google Cloud Platform).

This repository implements the plan described in `docs/`:
- `docs/RESEARCH.md` — state of the art, competitor analysis
- `docs/TECH_STACK.md` — technology comparisons and decisions
- `docs/PRD.md` — Product Requirements Document
- `docs/ARCHITECTURE.md` — system architecture with diagrams
- `docs/MILESTONES.md` — the 12-milestone build plan
- `docs/CLEAN_ARCHITECTURE.md` — project structure rationale

This repository currently contains the results of **Milestones 1–3**: the local-first infrastructure
foundation, the authentication/multi-tenancy layer (`auth-service`), and the data & storage foundation
(`catalog-service`). See `docs/MILESTONES.md` for the full plan and per-milestone status.

---

## Quickstart (local development)

No cloud account, credit card, or credentials are required to run this project locally.

**Prerequisites:** Docker (or Podman) with Compose support.

```
cp .env.example .env
docker compose up --build
```

This starts the backing services:
- `postgres` — PostgreSQL with the `pgvector` extension (system of record + small-scale vector search)
- `redis` — cache, queue backend, rate limiting
- `qdrant` — vector database (primary ANN search engine; used from Milestone 6)
- `minio` — S3-compatible object storage (stand-in for GCS/S3/Azure Blob)

…and the application services (each runs its own DB migrations on start):
- `auth-service` (`http://localhost:8001`) — tenants, API keys, access tokens, rate limiting
- `catalog-service` (`http://localhost:8002`) — catalog item metadata + signed-URL image storage

Once running, check readiness (verifies each service can reach its backends over the Compose network):
- `GET http://localhost:8001/readyz` — auth-service (postgres + redis)
- `GET http://localhost:8002/readyz` — catalog-service (postgres + object storage + auth-service)

**Provision a tenant and issue an API key**, then use it:

```
python scripts/provision_tenant.py --name my-tenant
# copy the printed API key, then:
curl -X POST http://localhost:8002/v1/items \
  -H "X-API-Key: <key>" -H "Content-Type: application/json" \
  -d '{"content_type":"image/jpeg","metadata":{"category":"demo"}}'
```

Tear down with `docker compose down` (add `-v` to also remove data volumes).

A `Makefile` wraps the common commands — run `make help` to see them (including `make db-backup` /
`make db-restore`, documented in `docs/RUNBOOK_BACKUP_RESTORE.md`).

---

## Repository layout

```
services/            Backend services. Implemented: auth-service (M2), catalog-service (M3).
                     Reserved: query, tenant, admin — populated in later milestones.
ai-service/           Embedding + reranking + fine-tuning service — populated from Milestone 5 onward
workers/              Background workers (ingestion, reindex, notification) — populated from Milestone 4 onward
frontend/             Web dashboard — populated from Milestone 11 onward
sdks/                 Client SDKs — populated from Milestone 11 onward
shared/               Minimal cross-service kernel + common libs (see docs/CLEAN_ARCHITECTURE.md, Section 5).
                     Implemented: domain-kernel (TenantId), common-libs (logging, JWT contract, gateway auth)
scripts/              Operational scripts (tenant provisioning, DB backup/restore)
tests/e2e/            Cross-service end-to-end tests
docs/                 Living planning documents (PRD, architecture, milestones, runbooks, etc.)
infra/                Infrastructure: Terraform (cloud-agnostic) + Kubernetes + CI definitions
```

---

## Infrastructure philosophy: local-first, cloud-agnostic

Every backing service used locally speaks an open, portable protocol rather than a cloud-proprietary API:

| Capability | Local (Docker Compose) | Production equivalent (any cloud) |
|---|---|---|
| Relational data + small-scale vectors | PostgreSQL + pgvector container | Cloud SQL / RDS / Azure Database for PostgreSQL |
| Cache / queue / rate limiting | Redis container | Memorystore / ElastiCache / Azure Cache for Redis |
| Object storage | MinIO container (S3 API) | GCS / S3 / Azure Blob |
| Vector search (scale tier) | Qdrant container | Qdrant Cloud / self-hosted Qdrant or Milvus on any cloud |

Because the application only ever talks to these systems via their open wire protocols (Postgres protocol,
Redis protocol, the S3 API), swapping what's *underneath* — a laptop container today, a managed cloud
service tomorrow — never requires touching application code. See `docs/CLEAN_ARCHITECTURE.md` Section 10 for
how this same dependency-inversion principle is enforced inside each service's codebase.

Cloud deployment (Terraform + Kubernetes, targeting GCP as the reference implementation, with AWS/Azure as
reserved sibling implementations) lives under `infra/` and is **fully prepared but never executed** during
development. See `infra/README.md` for details. Actual cloud deployment is deliberately deferred to a future
milestone, once the application is production-ready.

---

## CI/CD (Milestone 1 scope)

The pipeline (`.github/workflows/ci.yml`) runs on every push/PR and requires **no cloud account, credentials,
or billing**. It:

1. Builds the project
2. Runs formatting and lint checks
3. Runs unit tests
4. Builds the Docker image(s)
5. Validates the Docker Compose configuration
6. Brings the full stack up and verifies the application starts correctly (health + readiness checks)

Cloud deployment is intentionally **not** part of this pipeline yet — see `docs/MILESTONES.md` for when that
is introduced.
