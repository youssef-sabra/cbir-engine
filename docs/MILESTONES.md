# CBIR Engine — Project Milestone Plan
**12 Milestones, from foundation to GA launch — July 2026**

This plan sequences the PRD and architecture into 12 buildable milestones. Sequencing follows the dependency chain established in prior planning: infrastructure → data layer → ingestion → embedding → vector search → query API → caching → differentiation → observability → frontend → hardening → launch. Complexity is rated S / M / L / XL (roughly 1, 2, 4, and 6+ engineer-weeks respectively, for a small initial team).

---

## Milestone 1 — Foundations & DevOps Infrastructure

> **Status: ✅ Completed.** See `MILESTONE_1_COMPLETION_REPORT.md` for the full completion report,
> including acceptance-criteria evidence and known environment limitations.
>
> **Design note (superseding the original plan below the line):** this project is a solo-developer,
> production-quality portfolio project. Milestone 1 was deliberately re-scoped mid-implementation from an
> always-on-cloud design to a **local-first, cloud-agnostic** design: every backing service runs locally via
> Docker Compose (no cloud account, credentials, or billing required for day-to-day development), while
> Terraform and Kubernetes definitions are fully prepared under `infra/` for a future GCP-first (with
> AWS/Azure as reserved, documented sibling implementations) production deployment — never executed until a
> future milestone deliberately triggers it. The task list, deliverables, and acceptance criteria below are
> updated to reflect that final design; the original always-cloud framing is preserved in version history
> for context but no longer describes what was actually built.

**Objective:** Establish the repository, local development environment, containerization, and CI/CD
skeleton that every later milestone builds on — runnable entirely on a single developer's machine, with
cloud deployment infrastructure prepared but dormant.

**Features:**
- Local development stack via Docker Compose (PostgreSQL+pgvector, Redis, Qdrant, MinIO)
- Cloud-agnostic Terraform layout: contract-only module interfaces + a GCP reference implementation, with
  AWS/Azure reserved as documented, unimplemented siblings
- Cloud-agnostic Kubernetes layout: vanilla base manifests + a GCP overlay, with AWS/Azure reserved siblings
- CI/CD pipeline (build, lint, test, containerize, validate compose, verify startup) requiring no cloud
  account, credentials, or billing
- A throwaway `hello-world-service` proving the whole pipeline end to end before any real business logic
  exists

**Tasks:**
- Establish repository structure, branching strategy (trunk-based), and contribution conventions
- Define `docker-compose.yml` covering every backing service the architecture requires, each speaking an
  open wire protocol (Postgres protocol, Redis protocol, the S3 API) rather than a cloud-proprietary API
- Build `hello-world-service` (FastAPI, `/health` + `/readyz`) to validate the pipeline mechanics
- Define the Terraform module contracts (`modules/networking`, `modules/cluster`, `modules/data-services`)
  and implement them for GCP (`providers/gcp/...`), reserving `providers/aws/` and `providers/azure/`
- Define cloud-agnostic Kubernetes base manifests plus a GCP overlay, reserving AWS/Azure overlays
- Build the CI pipeline: build → lint/format → test → build Docker image → validate Compose → verify startup
  — explicitly with **no** deploy step
- Consolidate all prior planning documents into `docs/`

**Dependencies:** None — this is the starting point.

**Deliverables:**
- A runnable local stack (`docker compose up --build`) requiring zero cloud dependencies
- A CI pipeline that runs on every push/PR with no cloud credentials configured anywhere
- A cloud-agnostic `infra/` directory: Terraform (GCP implemented, AWS/Azure reserved) and Kubernetes
  manifests (GCP overlay implemented, AWS/Azure reserved), fully prepared but never executed
- `docs/MILESTONE_1_COMPLETION_REPORT.md` documenting exactly what was verified and how

**Acceptance Criteria:**
- CI pipeline builds the project, runs formatting/linting, and runs tests — with no manual steps
- CI pipeline builds Docker image(s), validates the Docker Compose configuration, and verifies the
  application starts correctly — again with no manual steps and no cloud dependency
- No cloud deployment occurs as part of this milestone
- No secret, credential, or cloud account is ever required to develop, test, or run CI for this project
- Terraform definitions for the GCP reference deployment (including explicit CPU/GPU node pool separation
  with taints) are complete, internally consistent, and syntactically valid — without requiring them to be
  applied against a real cluster during this milestone
- The infrastructure design avoids vendor lock-in structurally: every locally-run backing service speaks an
  open protocol, and cloud-specific implementation details are isolated behind a documented module/overlay
  interface

**Estimated Complexity:** M

**Actual outcome:** See `MILESTONE_1_COMPLETION_REPORT.md`. All 10 acceptance criteria are fully
satisfied. The two criteria originally blocked by the implementation sandbox's lack of container-registry
access (real image build; full multi-container Compose startup) were closed out on 2026-07-03 by running
the complete stack on the developer's own machine: the image built cleanly, all five containers reached
healthy, and `/readyz` confirmed every backing service reachable over the Compose network. The same
session also fixed a host-port/in-network-port conflation in `docker-compose.yml`, pinned the Qdrant and
MinIO image versions for reproducibility, and removed stale duplicate planning documents from the
repository root.

---

## Milestone 2 — Authentication, Multi-Tenancy & Tenant Management

> **Status: ✅ Completed.** See `MILESTONE_2_COMPLETION_REPORT.md`. Delivered as `services/auth-service`
> plus the `shared/domain-kernel` and `shared/common-libs` packages. All acceptance criteria verified by
> unit tests and against the live Docker Compose stack. "Deployed to staging" is interpreted as the
> local-first equivalent (running in the Compose stack), consistent with the Milestone 1 re-scope — no
> cloud staging environment exists yet by design.

**Objective:** Build the tenant, API key, and access-control foundation that every other service depends on for isolation and security.

**Features:**
- Tenant account creation and lifecycle
- API key issuance, scoping, and rotation
- Gateway-level token validation
- Rate limiting per tenant/key

**Tasks:**
- Design tenant/user/API-key data model in PostgreSQL
- Build Auth Service (issue/validate/revoke tokens and API keys)
- Implement gateway-level JWT validation middleware
- Implement Redis-backed rate limiting keyed by tenant/API key
- Build minimal internal tooling for manual tenant provisioning (pre-self-serve signup)

**Dependencies:** Milestone 1 (cluster, CI/CD, secrets management)

**Deliverables:**
- Auth Service deployed to staging
- API key issuance/rotation functioning end-to-end
- Rate limiting enforced and tested under load

**Acceptance Criteria:**
- A request with an invalid/expired key is rejected with a clear 401 and no downstream service is reached
- A tenant exceeding its configured rate limit receives a 429 within expected latency
- Tenant data isolation verified: tenant A's API key cannot access tenant B's resources under any tested path

**Estimated Complexity:** M

---

## Milestone 3 — Data Layer & Storage Foundation

> **Status: ✅ Completed.** See `MILESTONE_3_COMPLETION_REPORT.md`. Delivered as `services/catalog-service`
> (item metadata, signed-URL object storage, right-to-erasure deletion) plus the full data-layer schema
> (`catalog_items`, `embedding_refs`, `feedback`, `usage_records`, `adapter_versions`), the pgvector
> extension, and the backup/recovery baseline (`docs/RUNBOOK_BACKUP_RESTORE.md`, with an executed recovery
> drill). All acceptance criteria verified against the live stack. The retention/deletion *scaffolding*
> the plan mentions is delivered concretely as the working erasure endpoint.

**Objective:** Stand up the persistent storage layer (PostgreSQL, object storage) that catalog, billing, and metadata will depend on.

**Features:**
- PostgreSQL schema for tenants, catalog items, feedback, usage records
- Object storage integration for raw image uploads
- pgvector extension enabled for small-tenant vector workloads
- Backup and recovery baseline

**Tasks:**
- Finalize and migrate the PostgreSQL schema (tenant, catalog_item, embedding_ref, feedback, usage_record, adapter_version tables)
- Integrate S3-compatible object storage with signed upload/download URLs
- Enable and configure pgvector extension
- Configure automated backups with defined RPO/RTO
- Implement data retention/deletion workflow scaffolding (right-to-erasure hooks)

**Dependencies:** Milestone 1 (infrastructure); Milestone 2 (tenant model referenced by schema)

**Deliverables:**
- Migrated PostgreSQL schema in staging
- Object storage bucket(s) with working signed-URL upload/download flow
- Documented backup/recovery runbook

**Acceptance Criteria:**
- An image can be uploaded to object storage via signed URL and its metadata correctly persisted to PostgreSQL
- A simulated data-loss scenario is recoverable within the defined RTO using the documented runbook
- A test deletion request removes both the object storage file and associated metadata rows

**Estimated Complexity:** M

---

## Milestone 4 — Catalog Ingestion Pipeline

**Objective:** Build the asynchronous ingestion pipeline that takes uploaded images through deduplication and queuing, ready for embedding.

**Features:**
- Single and batch image upload API
- CSV/manifest-based catalog import
- Perceptual-hash deduplication
- Async job queue and status tracking

**Tasks:**
- Build Catalog & Ingestion Service (FastAPI) with upload, batch upload, and manifest import endpoints
- Implement perceptual-hash (pHash) deduplication before queuing
- Set up Redis-backed task queue and ingestion worker pool
- Implement job status tracking (pending/processing/indexed/failed) exposed via API
- Implement dead-letter queue and retry-with-backoff for failed ingestion jobs
- Implement optional object-centric cropping/segmentation step in the pipeline

**Dependencies:** Milestone 2 (auth for upload endpoints); Milestone 3 (object storage, PostgreSQL schema)

**Deliverables:**
- Working ingestion API accepting single/batch uploads and manifests
- Ingestion worker pool deployed and processing jobs from queue
- Dead-letter queue with alerting hook

**Acceptance Criteria:**
- A duplicate image (bit-identical or near-identical) is correctly detected and not double-processed
- 1,000 images submitted via batch upload are all reflected in job-status tracking with correct final states
- A deliberately malformed image fails gracefully, lands in the dead-letter queue, and does not crash the worker pool

**Estimated Complexity:** L

---

## Milestone 5 — Embedding Service & Model Integration

**Objective:** Stand up the AI service layer that turns images (and text) into vectors, using the selected foundation encoders.

**Features:**
- SigLIP 2 encoder deployed as primary embedding model
- DINOv2 encoder deployed as secondary structural embedding
- Batched inference for ingestion throughput
- Low-latency synchronous inference path for query-time embedding

**Tasks:**
- Deploy SigLIP 2 and DINOv2 as inference services on GPU node pool
- Implement batching for ingestion-time embedding calls
- Implement a lightweight, low-latency path for query-time single-image/text embedding
- Build the Inference Router that selects base encoder (and later, tenant adapter) per request
- Load-test embedding throughput and tune batch sizes/instance counts

**Dependencies:** Milestone 1 (GPU node pool); Milestone 4 (ingestion pipeline to feed embedding requests)

**Deliverables:**
- Embedding Service deployed to staging, callable by ingestion workers and query service (once built)
- Documented throughput benchmarks (images/sec at batch vs. single-image inference)
- Inference Router supporting model selection (initially base-model-only, adapter support stubbed for later milestone)

**Acceptance Criteria:**
- Batched ingestion embedding achieves the throughput improvement target versus naive per-image inference (documented in benchmark report)
- Query-time single-image embedding completes within the latency budget needed to hit overall P95 search latency targets
- Both SigLIP 2 and DINOv2 embeddings are correctly generated and stored with a model-version tag for traceability

**Estimated Complexity:** L

---

## Milestone 6 — Vector Database & ANN Search Integration

**Objective:** Integrate the vector database layer so embeddings generated in Milestone 5 are indexed and retrievable via approximate nearest-neighbor search.

**Features:**
- Qdrant deployed as the default per-tenant vector store
- Per-tenant collection isolation
- Metadata payload storage for hybrid (vector + filter) search
- Upsert and delete operations wired to the ingestion pipeline

**Tasks:**
- Deploy and configure Qdrant cluster (staging)
- Implement per-tenant collection creation and isolation logic
- Wire ingestion workers to upsert embeddings + metadata payload into Qdrant on successful embedding
- Implement item deletion/update propagation from PostgreSQL to Qdrant
- Write and validate ANN query interface (top-K retrieval with metadata filter) as an internal library, ahead of exposing it via the public Query API in Milestone 7
- Document the Qdrant → Milvus migration runbook (not yet triggered, but specified) referenced in the architecture plan

**Dependencies:** Milestone 5 (embeddings must exist to index); Milestone 3 (metadata schema)

**Deliverables:**
- Qdrant cluster in staging with live tenant collections
- Verified upsert/delete pipeline from ingestion through to vector store
- Internal ANN query library ready for the Query Service to call

**Acceptance Criteria:**
- An ingested item is retrievable via ANN search using its own image as the query, with itself (or a known near-duplicate) as the top result
- Deleting a catalog item removes its vector from Qdrant within a defined propagation SLA
- Metadata filters (e.g., category) correctly constrain ANN search results in test queries

**Estimated Complexity:** L

---

## Milestone 7 — Core Search API (Image & Text Query)

**Objective:** Expose the core customer-facing search capability: image-to-image and text-to-image search with metadata filtering, meeting baseline latency targets.

**Features:**
- Image-to-image search endpoint
- Text-to-image search endpoint
- Hybrid search (vector similarity + metadata filters)
- Ranked results with similarity scores, pagination, and relevance thresholds

**Tasks:**
- Build Query Service (FastAPI) orchestrating embed → ANN search → metadata enrichment → response
- Implement text-to-image query path using SigLIP 2's shared embedding space
- Implement metadata filter pass-through to the Qdrant query
- Implement pagination and minimum-relevance-threshold parameters
- Load-test the query path to validate P95 latency against NFR targets
- Write and publish OpenAPI specification for the search endpoints

**Dependencies:** Milestone 6 (vector search); Milestone 5 (query-time embedding); Milestone 2 (auth on endpoints)

**Deliverables:**
- Public (staging) Query API for image and text search
- Published OpenAPI spec and interactive docs
- Load-test report confirming latency against NFR1 target

**Acceptance Criteria:**
- A test image query returns a ranked, relevant result list within the P95 latency target at a representative catalog size
- A text query ("red running shoes") against a seeded catalog returns visually and semantically appropriate results
- Combining a metadata filter with a visual query correctly excludes non-matching items from results

**Estimated Complexity:** L

---

## Milestone 8 — Caching & Performance Optimization

**Objective:** Introduce the caching layer to reduce redundant compute on repeated queries and protect the AI service from unnecessary load.

**Features:**
- Query embedding cache
- Full result caching with TTL
- Cache invalidation on re-index
- Redis Cluster deployment for reliability

**Tasks:**
- Deploy Redis Cluster (replacing any single-instance Redis used in earlier milestones for queues)
- Implement query embedding cache (hash query image/text to cache key)
- Implement result caching with configurable TTL
- Implement cache invalidation triggers tied to item re-index/update events
- Load-test cache hit-rate impact on overall query latency and AI service load

**Dependencies:** Milestone 7 (query path exists to cache); Milestone 4 (re-index events must be identifiable to trigger invalidation)

**Deliverables:**
- Redis Cluster deployed to staging, serving cache and queue roles
- Documented cache hit-rate and latency improvement benchmarks
- Verified invalidation-on-reindex behavior

**Acceptance Criteria:**
- A repeated identical query returns from cache in under the defined cache-hit latency target, measurably faster than the uncached path
- Re-indexing an item invalidates any cached result referencing that item within a defined propagation window — a stale result is never served past that window
- Cache layer failure (simulated Redis outage) degrades gracefully to the uncached path rather than failing requests

**Estimated Complexity:** M

---

## Milestone 9 — Reranking & Compositional Query (Differentiation Layer)

**Objective:** Ship the product's core technical differentiator — starting with one of compositional query support or per-tenant fine-tuning per MVP scope, with the second staged as a fast-follow within this milestone's extended scope.

**Features:**
- Cross-encoder reranking on top-K shortlist
- MLLM-based reranking for compositional queries (image + text modification)
- Pluggable reranking selection (fast vs. precise mode)
- (Fast-follow) Per-tenant feedback collection and lightweight adapter fine-tuning

**Tasks:**
- Deploy cross-encoder reranking service and wire into the Query Service as an optional post-ANN-search step
- Deploy MLLM-based reranker for compositional queries; implement the query path accepting reference image + text modification
- Implement reranking-mode selection (per-tenant default or per-request override) per NFR17
- Build feedback submission endpoint (relevant/not relevant) and persist to PostgreSQL
- (Fast-follow) Build the fine-tuning/adapter training job and Adapter Store integration from the architecture plan
- (Fast-follow) Implement adapter versioning and rollback

**Dependencies:** Milestone 7 (base query path); Milestone 5 (embedding service, for MLLM/adapter integration); Milestone 8 (caching, since compositional queries are the most expensive path and benefit most from caching)

**Deliverables:**
- Compositional query endpoint functioning in staging with measurable quality improvement over naive retrieval
- Reranking mode selectable per tenant/request
- (Fast-follow) Working per-tenant fine-tuning pipeline producing a deployable adapter from submitted feedback

**Acceptance Criteria:**
- A composed query ("like this, but in blue") returns results that satisfy the stated modification in a sampled human-reviewed evaluation, at a defined success-rate threshold
- Compositional query P95 latency stays within the separate, more generous NFR2 target rather than blocking on the standard search SLA
- (Fast-follow) A tenant's fine-tuned adapter measurably improves Recall@K/nDCG on that tenant's held-out evaluation set versus the base model

**Estimated Complexity:** XL

---

## Milestone 10 — Monitoring, Logging & Observability

**Objective:** Instrument the full system so latency, errors, cost, and retrieval quality are visible and alertable before real customer traffic arrives.

**Features:**
- Metrics collection and dashboards
- Distributed tracing across the multi-hop query path
- Centralized structured logging with PII scrubbing
- Alerting tied to NFR thresholds

**Tasks:**
- Deploy Prometheus and instrument all services (API, workers, AI service, Qdrant, Redis) with metrics
- Build Grafana dashboards for latency percentiles, uptime, cost-per-1,000-queries, ingestion throughput, GPU utilization
- Deploy OpenTelemetry tracing across the Gateway → Query → Embedding → VectorDB → Reranker path
- Deploy centralized log aggregation (Loki/ELK) with structured JSON logging and PII/image-content scrubbing
- Configure Alertmanager rules tied to NFR thresholds (latency breach, uptime risk, DLQ depth, GPU saturation)
- Set up on-call rotation and runbook links from alerts

**Dependencies:** Milestones 1–9 (there must be a working system to instrument)

**Deliverables:**
- Full observability stack deployed to staging and production
- Documented dashboards mapped to each NFR
- Verified alert firing and on-call notification for at least one simulated incident per alert type

**Acceptance Criteria:**
- A deliberately injected latency regression is visible on the relevant dashboard and triggers the corresponding alert within the expected detection window
- A trace for a single query request is fully visible end-to-end across all five hops in the tracing backend
- No raw image content or unscrubbed PII appears in centralized logs under audit

**Estimated Complexity:** M

---

## Milestone 11 — Frontend Dashboard, SDKs & Developer Experience

**Objective:** Build the self-serve surface — dashboard, documentation, and SDKs — that lets a new developer go from signup to first successful query in under 15 minutes.

**Features:**
- Web dashboard: signup, API key management, catalog browsing, usage/cost visibility, search playground
- Primary-language SDK (Python or JavaScript, per MVP scope)
- Interactive API documentation
- Self-serve onboarding flow

**Tasks:**
- Build React SPA dashboard covering signup, API key management, and basic catalog view
- Build a usage/cost dashboard view backed by the Tenant & Billing Service and metrics from Milestone 10
- Build a search playground in the dashboard that calls the same public Query API
- Publish the primary SDK with authentication, upload, and search wrapper methods
- Finalize interactive API documentation (Swagger/ReDoc) linked from the dashboard
- Build and test the full self-serve onboarding flow end-to-end

**Dependencies:** Milestone 2 (auth/API keys); Milestone 7 (query API); Milestone 4 (ingestion API); Milestone 10 (usage metrics to display)

**Deliverables:**
- Deployed web dashboard (staging, then production)
- Published SDK package (versioned, documented)
- Verified self-serve onboarding flow

**Acceptance Criteria:**
- A test user with no prior context can sign up, obtain an API key, ingest a test image, and receive search results within 15 minutes using only self-serve documentation (NFR20)
- The SDK's search and ingestion methods work correctly against the production API without undocumented behavior
- Usage dashboard numbers match the underlying metering/billing records within an acceptable tolerance

**Estimated Complexity:** L

---

## Milestone 12 — Beta Hardening, Security Review & GA Launch

**Objective:** Convert the staging-proven system into a production-hardened, security-reviewed, customer-ready product, and execute the design-partner-to-GA transition.

**Features:**
- Production deployment with canary rollout capability
- Security review and remediation
- Design-partner onboarding and feedback loop
- Retrieval-quality benchmark validation gating GA

**Tasks:**
- Execute full production deployment following the canary rollout process defined in the architecture plan
- Conduct a security review (data isolation, encryption at rest/in transit, dependency audit, access control review) and remediate findings
- Finalize data retention/deletion workflows end-to-end (right-to-erasure) and verify against NFR13/NFR14
- Onboard 3–5 design-partner tenants to production; collect structured feedback
- Run the retrieval-quality benchmark suite (Recall@K, nDCG) against each design partner's vertical evaluation set and confirm it meets internal thresholds
- Finalize pricing/billing metering accuracy audit
- Prepare GA launch materials (documentation completeness check, status page, support process)

**Dependencies:** All prior milestones (1–11) — this is the integration and launch-readiness milestone.

**Deliverables:**
- Production system serving design-partner traffic
- Security review report with remediations closed or explicitly risk-accepted
- GA launch readiness checklist, fully signed off

**Acceptance Criteria:**
- At least 3–5 design-partner tenants are actively querying in production with no P0/P1 incidents open
- Security review has no unresolved critical or high findings
- Retrieval-quality benchmarks meet or exceed the internal thresholds defined in the PRD's MVP success criteria on at least one target vertical
- Billing/usage metering matches actual API usage within the defined tolerance for at least one full billing cycle in staging or design-partner production use

**Estimated Complexity:** XL

---

## Milestone Summary Table

| # | Milestone | Complexity | Key Dependency | Status |
|---|---|---|---|---|
| 1 | Foundations & DevOps Infrastructure | M | — | ✅ Completed |
| 2 | Authentication, Multi-Tenancy & Tenant Management | M | M1 | ✅ Completed |
| 3 | Data Layer & Storage Foundation | M | M1, M2 | ✅ Completed |
| 4 | Catalog Ingestion Pipeline | L | M2, M3 | ✅ Completed |
| 5 | Embedding Service & Model Integration | L | M1, M4 | ✅ Completed (real SigLIP 2 encoder; OpenCLIP/DINOv2 alt; local = offline/CI fallback) |
| 6 | Vector Database & ANN Search Integration | L | M3, M5 | ✅ Completed |
| 7 | Core Search API (Image & Text Query) | L | M2, M5, M6 | ✅ Completed |
| 8 | Caching & Performance Optimization | M | M4, M7 | ✅ Completed |
| 9 | Reranking & Compositional Query (Differentiation) | XL | M5, M7, M8 | ✅ Core completed (MLLM rerank + fine-tuning = seams) |
| 10 | Monitoring, Logging & Observability | M | M1–M9 | ✅ Completed (Prometheus metrics + Grafana + alerts + request-id tracing) |
| 11 | Frontend Dashboard, SDKs & Developer Experience | L | M2, M4, M7, M10 | ✅ Completed (Python SDK + build-free dashboard + Swagger docs) |
| 12 | Beta Hardening, Security Review & GA Launch | XL | M1–M11 | ✅ Completed (security review + hardening, retrieval-quality gate, GA checklist) |

**Critical path:** M1 → M2 → M3 → M4 → M5 → M6 → M7 → M9 → M12, with M8, M10, and M11 running partially in parallel once their respective dependencies (M7, M4/M7/M9, M2/M4/M7) are satisfied — a small team can compress the overall timeline by starting M10's instrumentation work incrementally alongside M4–M9 rather than waiting for all of them to complete.
