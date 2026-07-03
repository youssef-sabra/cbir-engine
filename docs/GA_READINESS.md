# GA Readiness Checklist (Milestone 12)

Tracks the launch-readiness state of the platform. This is a solo-developer, production-quality portfolio
build run entirely local-first; "staging/production" items are satisfied by the local Compose stack plus
the prepared-but-dormant `infra/` (Terraform + Kubernetes), which a real deployment milestone would apply.

## Engineering

- [x] All 12 milestones implemented (see `docs/MILESTONES.md`).
- [x] Every service follows Clean Architecture with unit tests using in-memory fakes.
- [x] Full unit suite green; lint (ruff) clean across every package.
- [x] Cross-service e2e suite (tenant isolation, storage round trip) green against the live stack.
- [x] Full ingest → index → search pipeline smoke test green against the live stack.
- [x] CI runs build → lint → test (matrix) → image build → compose up → readiness → metrics → smoke, with
      no cloud credentials.

## Retrieval quality (CBIR-specific gate)

- [x] Recall@K / Precision@K / MRR / nDCG@K harness with configurable thresholds
      (`infra/ci/quality-gates/retrieval_quality.py`), unit-tested.
- [x] Real semantic encoder available and verified (SigLIP 2 — see `docs/AI_PIPELINE_UPGRADE.md`).
- [ ] Per-vertical benchmark eval sets curated from real labelled data (fixture only today — the gate math
      is proven; real eval data is a data-collection task with design partners).

## Reliability & operations

- [x] Health (`/health`) and readiness (`/readyz`) on every service; dependency reachability surfaced.
- [x] Observability: Prometheus metrics + Grafana dashboard + NFR-tied alert rules (Milestone 10).
- [x] Ingestion retry/backoff + dead-letter queue; DLQ depth is alertable.
- [x] Backup/restore runbook with an executed recovery drill (`docs/RUNBOOK_BACKUP_RESTORE.md`).
- [x] Graceful degradation: rate-limiter and query cache fail open on Redis outage.

## Security & data

- [x] Security review completed with findings remediated (`docs/SECURITY_REVIEW.md`).
- [x] Tenant isolation verified end to end.
- [x] Right-to-erasure (object + metadata) verified.
- [x] Non-root containers; pinned images; no secrets in the repo.
- [ ] TLS + managed secret storage — deployment-milestone items (infra prepared, not applied).

## Developer experience

- [x] Python SDK (`cbir`) with tests.
- [x] Self-serve dashboard (catalog + search playground).
- [x] Interactive API docs per service (`/docs` Swagger, `/openapi.json`).
- [x] One-command local bring-up (`docker compose up --build`) with zero cloud dependencies.

## Deliberately deferred (post-GA / future scope)

- Cloud deployment execution (Terraform apply, GKE rollout, canary) — infra is prepared and dormant.
- JS/TS SDK; full React SPA with signup/billing; MLLM-based reranking; per-tenant fine-tuning training.
- Real design-partner onboarding and live traffic (out of scope for a local build).

**Status:** GA-ready as a local-first, production-quality reference implementation. The only gates to a real
public launch are the deployment-milestone items above (cloud apply, TLS/secrets, real benchmark data),
each of which has a prepared path.
