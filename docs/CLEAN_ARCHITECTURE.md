# CBIR Engine — Clean Architecture Project Structure
**Folder-by-folder and module-by-module rationale — July 2026**

---

## 0. Why Clean Architecture for This Project Specifically

Before the structure itself, it's worth being explicit about *why* this pattern was chosen, because every folder below exists to serve one of these reasons:

- **Swappable AI/infra components.** The PRD requires the embedding model (NFR16) and reranking strategy (NFR17) to be replaceable without re-architecture, and the tech-stack plan explicitly treats the vector database as a swappable component (Qdrant → Milvus migration). Clean Architecture's dependency rule — inner layers never depend on outer, technology-specific layers — is precisely the mechanism that makes this possible. The domain logic ("what makes two images similar enough to rank") must never import a Qdrant client or a SigLIP model directly.
- **Independent testability.** Retrieval-quality regression tests (introduced in the CI/CD milestone) need to exercise business rules — ranking logic, relevance thresholds, tenant quota rules — without spinning up a real vector database, GPU, or Redis instance. This is only possible if that logic lives in framework-independent layers.
- **Multiple delivery mechanisms over one core.** The same search/ranking logic is invoked by the public REST API, the internal admin tool, and (eventually) the SDKs. Clean Architecture's separation of use cases from interface adapters means this logic is written once and exposed through multiple "frameworks & drivers" without duplication.
- **Long-lived core, disposable edges.** Foundation encoders, vector databases, and even the web framework are all things this product is likely to change over its lifetime (the CBIR research itself found the field moving quickly). Clean Architecture is built on the premise that frameworks and databases are details; the structure below keeps them at the edges, literally and organizationally.

The four canonical Clean Architecture layers are applied consistently across every backend service and the AI service:

1. **Domain (Entities)** — enterprise-wide business rules and core objects, with zero external dependencies.
2. **Application (Use Cases)** — application-specific business rules; orchestrates domain objects to fulfill a specific operation.
3. **Interface Adapters** — converts data between use cases and the outside world (controllers, presenters, gateways/repository implementations' interfaces).
4. **Frameworks & Drivers** — the outermost layer: web framework, database driver, ML inference runtime, message queue client, UI.

Dependencies always point inward. Outer layers know about inner layers; inner layers know nothing about outer layers.

---

## 1. Top-Level Repository Layout

```
cbir-engine/
├── services/
│   ├── auth-service/
│   ├── catalog-service/
│   ├── query-service/
│   ├── tenant-service/
│   └── admin-service/
├── ai-service/
├── workers/
│   ├── ingestion-worker/
│   ├── reindex-worker/
│   └── notification-worker/
├── frontend/
│   └── dashboard/
├── sdks/
│   ├── python-sdk/
│   └── js-sdk/
├── shared/
│   ├── domain-kernel/
│   └── common-libs/
├── infra/
│   ├── kubernetes/
│   ├── terraform/
│   └── ci/
├── tests/
│   └── e2e/
└── docs/
```

### Why a monorepo of independently deployable services (rather than one monolith, or many separate repos)

- **Independently deployable, but not independently *architected*.** Each service in `services/` and `ai-service/` is a separately deployed unit (matching the Kubernetes deployment plan), but all of them follow the identical internal Clean Architecture layout described in Section 3. A monorepo lets that shared layout, and the `shared/` kernel, be enforced and refactored consistently rather than drifting across repos.
- **Matches the architecture document's service boundaries.** `auth-service`, `catalog-service`, `query-service`, and `tenant-service` map directly to the Auth Service, Catalog & Ingestion Service, Query/Search Service, and Tenant & Billing Service defined in the architecture. This is deliberate: the folder structure should never surprise someone who has already read the architecture diagrams.
- **Workers and AI service are separated from request-serving services** because they scale on different axes (queue depth and GPU utilization, respectively, vs. request concurrency) and are deployed to different node pools — keeping them as distinct top-level units mirrors that operational reality.

---

## 2. Top-Level Folder Explanations

### `services/`
Houses every request-serving backend service. Each is independently deployable, independently scalable, and — critically — each internally follows the same four-layer Clean Architecture structure (detailed in Section 3), so a developer who understands one service's layout understands all of them.

- **`auth-service/`** — Owns tenant identity, API key lifecycle, token issuance/validation, and rate-limit policy. Exists as its own service because authentication is a cross-cutting concern every other service depends on, and isolating it lets it be hardened, audited, and scaled (it sits on the hot path of every single request) independently of business-logic-heavy services.
- **`catalog-service/`** — Owns catalog item lifecycle: upload intake, metadata CRUD, deduplication triggering, and handing work to the ingestion queue. Exists separately from `query-service` because ingestion and query have entirely different load profiles and failure tolerances — a catalog upload spike must never degrade search latency, and separating the services (and their deployments) is what makes that guarantee enforceable rather than aspirational.
- **`query-service/`** — Owns the core customer-facing search request: orchestrating embedding, ANN search, filtering, and reranking into a ranked response. This is the most latency-sensitive service in the system and is kept as lean and singly-focused as possible for that reason.
- **`tenant-service/`** — Owns tenant account lifecycle, plan/quota configuration, usage metering, and billing integration. Separated from `auth-service` because identity/access and commercial/billing concerns change for different reasons and at different rates — billing logic shouldn't require redeploying the authentication hot path, and vice versa.
- **`admin-service/`** — The internal back-office tool (Django, per the architecture decision to keep heavier synchronous tooling off the customer-facing async path). Exists as a separate service specifically so its different technology choice and different (lower) performance requirements never bleed into the performance-critical services.

### `ai-service/`
Houses embedding generation, reranking, and per-tenant fine-tuning/adapter management. Kept separate from `services/` because it has a fundamentally different runtime profile (GPU-bound, model-loading, batch-oriented) and deployment target (GPU node pool) than the request-serving CPU services. Internally, it follows the same Clean Architecture layering as the other services (Section 3) — the domain concept of "produce a vector representation of this image" is kept independent of whether that vector comes from SigLIP 2, DINOv2, or a future replacement model.

### `workers/`
Houses all asynchronous background processing, split into three focused units:
- **`ingestion-worker/`** — Consumes the ingestion queue, calls the AI service to embed, and writes to the vector database and PostgreSQL. Separated from the `catalog-service` that enqueues the work, so ingestion throughput scales independently of the upload API's request-handling capacity.
- **`reindex-worker/`** — Handles full/partial catalog re-indexing and scheduled fine-tuning jobs. Separated from `ingestion-worker` because re-indexing is typically bulk, scheduled, and resource-intensive in a different way than steady-state per-item ingestion, and the two should be capacity-planned and scaled independently.
- **`notification-worker/`** — Delivers webhooks and async events. Kept separate because its failure modes (a customer's webhook endpoint being down) and retry semantics are unrelated to the embedding/indexing pipeline's failure modes, and a backlog in one should never block the other.

### `frontend/`
Houses the customer-facing web dashboard. Kept as its own top-level unit (rather than nested inside a backend service) because it is built and deployed as a static SPA via CDN — an entirely different build/deploy pipeline than any backend service, per the architecture's frontend design decision.

### `sdks/`
Houses the client libraries distributed to customers. Separated from `frontend/` and `services/` because SDKs are published as independent versioned packages with their own release cadence and semantic-versioning contract, distinct from the internal services' deployment cadence.

### `shared/`
Houses code genuinely shared across multiple services — but deliberately kept small (see Section 5), because over-sharing across service boundaries is one of the most common ways a "microservices with Clean Architecture" project quietly turns back into a tightly coupled monolith.

### `infra/`
Houses Kubernetes manifests/Helm charts, Terraform IaC, and CI/CD pipeline definitions. Kept entirely separate from application code because infrastructure changes (a node pool resize, a CI runner update) should never require touching, reviewing, or redeploying application logic, and vice versa — this is the "Frameworks & Drivers" layer applied at the whole-system level, not just within a single service.

### `tests/e2e/`
Houses cross-service end-to-end tests (e.g., "upload an image, wait for indexing, issue a search, verify the result") that by definition cannot live inside any single service's own test suite, since they exercise the whole system.

### `docs/`
Houses the PRD, architecture document, milestone plan, and this structure document itself, plus API reference material — kept in the repo (not an external wiki) so documentation changes are reviewed alongside the code changes that necessitate them.

---

## 3. Canonical Per-Service Internal Structure

This layout is repeated, with only naming variations, inside every service under `services/` and inside `ai-service/`. Explained once here in full; Section 4 notes what specifically lives in each layer per service.

```
<service-name>/
├── domain/
│   ├── entities/
│   ├── value_objects/
│   ├── domain_services/
│   └── repository_interfaces/
├── application/
│   ├── use_cases/
│   ├── dto/
│   └── ports/
├── interface_adapters/
│   ├── controllers/
│   ├── presenters/
│   ├── gateways/
│   └── mappers/
├── infrastructure/
│   ├── persistence/
│   ├── external_clients/
│   ├── messaging/
│   └── config/
└── entrypoint/
    └── composition_root/
```

### `domain/` — Layer 1: Entities

The innermost layer. Contains the enterprise-wide concepts that would still make sense even if this were a completely different kind of application (a desktop tool, a CLI, a different API framework entirely). Has **zero dependencies** on anything else in the service — no web framework, no database driver, no ML library imports.

- **`entities/`** — The core business objects: e.g., `CatalogItem`, `Tenant`, `SearchQuery`, `RankedResult`, `Embedding` (as a value-carrying concept — a vector plus its model provenance, not a database row). These exist because they are the vocabulary the entire business is described in, independent of how they're stored or served.
- **`value_objects/`** — Immutable, self-validating concepts with no identity of their own: e.g., `SimilarityScore`, `RelevanceThreshold`, `TenantQuota`, `APIKeyScope`. These exist to make invalid states unrepresentable (a `SimilarityScore` cannot be constructed outside its valid range) rather than relying on scattered validation logic.
- **`domain_services/`** — Business logic that doesn't naturally belong to a single entity: e.g., a ranking-tiebreak policy, a deduplication-equivalence rule. These exist because not all business rules are naturally a method on one object — some genuinely operate across several.
- **`repository_interfaces/`** — Abstract interfaces (ports) describing what persistence operations the domain needs (`CatalogItemRepository.find_by_id`, `EmbeddingRepository.upsert`) **without specifying how**. These exist so the domain and application layers can depend on an abstraction rather than on PostgreSQL, Qdrant, or any specific technology — this is the single most important mechanism enabling the "swap the vector database" requirement from the NFRs.

### `application/` — Layer 2: Use Cases

Contains application-specific business rules — the orchestration logic for a specific operation the system performs. Depends only on `domain/`.

- **`use_cases/`** — One module per distinct operation: e.g., `IngestCatalogItem`, `SearchByImage`, `SearchByText`, `SearchComposed`, `SubmitRelevanceFeedback`, `IssueAPIKey`, `RotateAPIKey`. Each use case orchestrates domain entities and calls repository interfaces (never concrete implementations) to fulfill exactly one operation. These exist as the direct, literal expression of the PRD's functional requirements and user stories — there should be a near 1:1 traceable line from an FR/user story to a use case module.
- **`dto/`** (Data Transfer Objects) — Plain data structures used to pass information into and out of use cases, decoupled from both the domain entities (which shouldn't be mutated arbitrarily by outer layers) and from any API request/response schema (which belongs to the web framework, an outer layer). These exist to prevent the domain entities from being contorted to match whatever shape an API framework or database ORM happens to want.
- **`ports/`** — Additional abstract interfaces beyond repositories that use cases need — e.g., an `EmbeddingProviderPort`, a `RerankingProviderPort`, a `NotificationPort`. These exist for the same reason as `repository_interfaces/`: the use case "search by image" should be expressible without knowing whether embedding is done by SigLIP 2 or a future replacement.

### `interface_adapters/` — Layer 3: Interface Adapters

Converts data between the format most convenient for use cases/entities and the format most convenient for external agencies (web, database, ML runtime). Depends on `application/` and `domain/`, and defines the concrete shape that `infrastructure/` will plug into.

- **`controllers/`** — Receive incoming requests (from the web framework, in the outermost layer) and translate them into use-case invocations. These exist as the *only* place in the codebase that knows both "what an HTTP request looks like" and "what a use case needs" — keeping that translation out of the use cases themselves is what allows the same use case to be invoked from a REST controller, an internal admin tool, or a test harness identically.
- **`presenters/`** — Translate use-case output (DTOs) into the response shape a specific delivery mechanism needs (a JSON API response, an internal RPC response). Kept separate from controllers because request-shaping and response-shaping are genuinely different responsibilities with different failure modes (input validation vs. output formatting).
- **`gateways/`** — Concrete implementations of the `repository_interfaces/` and `ports/` defined in the inner layers, but only the interface-facing half — the part that adapts, e.g., a generic `CatalogItemRepository` interface to "how do I talk to whatever storage technology infrastructure/ provides." These exist as the seam where the dependency-inversion actually happens: the gateway implements the inner-layer interface but is free to depend on the outer `infrastructure/` layer to do the real work.
- **`mappers/`** — Convert between domain entities and the wire/storage formats used at the boundary (e.g., entity ↔ ORM model, entity ↔ external API payload). These exist to keep the mapping logic itself testable and in one place, rather than scattered inline wherever data crosses a boundary.

### `infrastructure/` — Layer 4: Frameworks & Drivers

The outermost layer — all concrete, swappable technology. This is the only layer allowed to import a specific web framework, database driver, ML library, or message queue client.

- **`persistence/`** — Concrete database access code: PostgreSQL/pgvector queries via SQLAlchemy (for `catalog-service`, `tenant-service`, `auth-service`), and Qdrant/Milvus client calls (for `query-service`, `ingestion-worker`). This is the layer that would change entirely if the Qdrant → Milvus migration described in the architecture plan is executed — and because `domain/` and `application/` never import from here directly, that migration touches only this folder plus its corresponding `gateways/` implementation.
- **`external_clients/`** — HTTP/gRPC clients for calling other internal services (e.g., `query-service` calling `ai-service`) and any third-party integrations (billing provider, email provider for notifications).
- **`messaging/`** — Redis queue producer/consumer implementations, webhook delivery mechanics. Exists separately from `persistence/` because message-queue semantics (at-least-once delivery, retry/backoff) are a distinct concern from data storage semantics.
- **`config/`** — Environment-specific configuration loading (secrets, feature flags, per-environment endpoints). Kept isolated so that no other layer ever reads an environment variable directly — configuration is read once, here, and passed inward as plain values.

### `entrypoint/`

- **`composition_root/`** — The single place in the service where all the concrete implementations from `infrastructure/` are wired up and injected into the use cases and controllers via their abstract interfaces. This exists as a deliberate, singular "wiring" location so that dependency injection isn't scattered — anyone wanting to understand "which concrete vector database implementation is actually plugged in right now" has exactly one file to check. This is also where the FastAPI (or Django, for `admin-service`) application object itself is constructed and where routes are registered to controllers.

---

## 4. What Lives Where, Per Service

| Service | Notable domain entities | Notable use cases | Notable infrastructure |
|---|---|---|---|
| `auth-service` | `Tenant`, `APIKey`, `RateLimitPolicy` | `IssueAPIKey`, `ValidateToken`, `RotateAPIKey`, `CheckRateLimit` | PostgreSQL (tenant/key tables), Redis (rate-limit counters, revocation list) |
| `catalog-service` | `CatalogItem`, `IngestionJob` | `UploadItem`, `ImportManifest`, `DeduplicateItem`, `RequestReindex` | Object storage client, PostgreSQL, Redis queue producer |
| `query-service` | `SearchQuery`, `RankedResult`, `SimilarityScore` | `SearchByImage`, `SearchByText`, `SearchComposed`, `ApplyMetadataFilter` | Qdrant/Milvus client, Redis cache client, `ai-service` client |
| `tenant-service` | `Tenant`, `Plan`, `UsageRecord` | `CreateTenant`, `RecordUsage`, `EnforceQuota`, `GenerateInvoiceData` | PostgreSQL, billing-provider client |
| `admin-service` | (reuses domain entities via shared kernel, read-mostly) | `ModerateCatalogItem`, `ReviewTenantAccount` | Django ORM against the same PostgreSQL instance (read/limited-write) |
| `ai-service` | `Embedding`, `AdapterVersion`, `RerankRequest` | `GenerateEmbedding`, `RerankShortlist`, `TrainTenantAdapter` | Model-serving runtime (SigLIP 2/DINOv2 weights), Adapter Store, GPU scheduling |

---

## 5. `shared/` — What Belongs Here (and Why So Little Does)

- **`domain-kernel/`** — A small number of *genuinely* universal concepts referenced by more than one service's domain layer without contradiction: e.g., a `TenantId` value object, a common `ModelVersion` tag format used by both `ai-service` and `catalog-service` to record provenance. Kept deliberately minimal — the temptation to put "shared" business logic here is exactly how service boundaries erode; something only belongs here if duplicating it across services would create a genuine correctness risk (e.g., two different definitions of what a valid `TenantId` looks like), not merely to avoid retyping a class.
- **`common-libs/`** — Cross-cutting technical utilities with no business meaning: structured logging setup, OpenTelemetry tracing helpers, standard error-response formatting. These exist here (rather than duplicated per service) because they are pure infrastructure concerns with no domain content — sharing them creates no coupling between services' business logic, only consistency in their operational behavior.

---

## 6. `frontend/dashboard/` Structure

The frontend does not follow the same four-layer backend structure verbatim (it has no domain entities of its own — it's a client of the backend's domain), but applies the same underlying principle: keep framework-specific code (React, routing, styling) at the edges and business-facing logic (what a "search result" looks like, what "usage" means) in a testable core.

```
dashboard/
├── core/
│   ├── models/
│   └── api-client/
├── features/
│   ├── onboarding/
│   ├── catalog-management/
│   ├── search-playground/
│   └── usage-billing/
└── ui/
    ├── components/
    └── layouts/
```

- **`core/models/`** — Typed representations of backend concepts as seen by the frontend (a `SearchResult`, a `UsageSummary`) — exists to give the frontend its own stable vocabulary, decoupled from raw API response shapes, mirroring the DTO principle from the backend.
- **`core/api-client/`** — The single place that calls the backend API (effectively the frontend's own thin SDK usage), so no component reaches out to the network directly.
- **`features/`** — Organized by user-facing capability (mirroring the PRD's user stories directly: onboarding, catalog management, search playground, usage/billing) rather than by technical type, so a change to "the search playground" touches one folder, not scattered files across the codebase.
- **`ui/`** — Purely presentational components and layouts with no business logic, kept separate so they remain reusable and trivially testable in isolation.

---

## 7. `sdks/` Structure

```
sdks/
├── python-sdk/
│   ├── client/
│   └── models/
└── js-sdk/
    ├── client/
    └── models/
```

- **`client/`** (per SDK) — The thin wrapper around HTTP calls to the public API, handling auth token attachment and retries. Exists as a deliberately minimal layer — the SDK should not contain business logic, only convenience over the already-well-designed public API.
- **`models/`** (per SDK) — Typed request/response models mirroring the public OpenAPI spec, generated or hand-maintained to stay in sync with `query-service` and `catalog-service`'s public contracts.

---

## 8. `infra/` Structure

```
infra/
├── kubernetes/
│   ├── base/
│   └── overlays/
├── terraform/
│   ├── networking/
│   ├── cluster/
│   └── data-services/
└── ci/
    ├── pipelines/
    └── quality-gates/
```

- **`kubernetes/base/`** and **`overlays/`** — Base manifests plus environment-specific overlays (staging, production), following a standard Kustomize-style separation so environment differences are explicit and reviewable rather than hidden in conditional logic.
- **`terraform/networking/`, `cluster/`, `data-services/`** — Split by infrastructure concern so a networking change and a managed-database change are reviewed and applied independently, reducing blast radius.
- **`ci/pipelines/`** — The build/test/deploy pipeline definitions per service.
- **`ci/quality-gates/`** — Specifically houses the retrieval-quality regression gate (Recall@K/nDCG benchmark) configuration from the CI/CD milestone plan — kept as its own distinct folder because it is a CBIR-specific gate, not a generic test suite, and deserves to be visible as a first-class part of the pipeline rather than buried inside a generic "tests" step.

> **Superseded by the Milestone 1 implementation.** The `terraform/` layout above (flat
> `networking/`/`cluster/`/`data-services/`) was refined during Milestone 1 into an explicit
> interface/implementation split — `terraform/modules/` (contract-only: variables and outputs, no
> resources), `terraform/providers/<cloud>/` (per-cloud implementations, GCP filled in first, AWS/Azure
> reserved), and `terraform/environments/<name>/` (root modules wiring a provider implementation together)
> — specifically to satisfy a stronger vendor-lock-in-avoidance requirement than originally specified here.
> Similarly, `kubernetes/overlays/` no longer includes a `staging/` overlay, since local development runs
> entirely on Docker Compose rather than a local or shared staging Kubernetes cluster; it instead contains
> per-cloud overlays (`gcp/` implemented, `aws/`/`azure/` reserved). See `infra/README.md` in the repository
> for the authoritative, current structure and the reasoning behind this refinement.

---

## 9. `tests/e2e/` Structure

```
tests/e2e/
├── ingestion_to_search/
├── multi_tenancy_isolation/
└── compositional_query/
```

Each subfolder corresponds to a cross-service journey that cannot be validated by any single service's own test suite: the full ingest→embed→index→search loop, verification that tenant data isolation holds across every service boundary, and the compositional-query path spanning `query-service` and `ai-service` together. These exist as the direct test-level embodiment of the acceptance criteria defined in the milestone plan (e.g., "tenant A's API key cannot access tenant B's resources under any tested path").

---

## 10. How This Structure Enforces the Dependency Rule in Practice

The single rule that makes all of the above worth doing: **source code dependencies can only point inward.** Concretely, in every service:

- `domain/` imports nothing from this service's other folders.
- `application/` imports only from `domain/`.
- `interface_adapters/` imports from `application/` and `domain/`.
- `infrastructure/` imports from `interface_adapters/` (to implement its interfaces) and may import any external library/framework.
- `entrypoint/` is the only place allowed to import from every layer at once, because its sole job is wiring them together.

This is what makes the NFR16/NFR17 swappability requirements achievable as a structural property of the codebase rather than a matter of developer discipline: replacing Qdrant with Milvus, or SigLIP 2 with a future encoder, is a change confined to `infrastructure/` (and its corresponding `gateways/` implementation) in exactly one service, with `domain/`, `application/`, and every other service completely unaware the change happened.
