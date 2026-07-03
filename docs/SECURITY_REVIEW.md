# Security Review (Milestone 12)

A self-review of the platform's security posture, the controls in place, and the remediations applied.
Scope: the application and its local-first stack. TLS termination, network policy, and secret storage are
deployment concerns handled by the `infra/` layer at the deployment milestone.

## Controls in place

| Area | Control |
|---|---|
| **AuthN** | API keys `cbir_<id>_<secret>`; only a SHA-256 hash of the 256-bit secret is stored; full key shown once. Short-lived HS256 access tokens with a Redis revocation list. |
| **AuthZ** | Scoped keys (`catalog:read`/`catalog:write`/`search:query`); every resource endpoint enforces its required scope via the gateway-role dependency. |
| **Tenant isolation** | Repository interfaces are tenant-scoped *by signature* — cross-tenant access is structurally inexpressible; per-tenant Qdrant collections; verified by the multi-tenancy e2e suite. |
| **Rate limiting** | Redis fixed-window per API key; 429 with `Retry-After`. |
| **Data-at-rest / erasure** | Right-to-erasure endpoint removes the object then cascades metadata (NFR13), verified live. |
| **PII in logs** | Structured JSON logging; raw image bytes and secrets are never logged (NFR14). |
| **Containers** | All service images run as a non-root user; images pinned. |
| **Input limits** | Query image uploads capped (20 MB); batch size capped (1000); unknown content types rejected (422). |

## Findings & remediations (this review)

| # | Finding | Severity | Remediation |
|---|---|---|---|
| S1 | No baseline security response headers | Low | Added `SecurityHeadersMiddleware` (`X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Cache-Control`) to every service. |
| S2 | CORS defaulted implicitly | Medium | CORS is now explicit and configurable (`CORS_ALLOW_ORIGINS`); `*` in local dev, **must** be restricted to the dashboard origin in production. |
| S3 | Dev default secrets could silently reach production | Medium | auth-service logs a loud startup warning if `AUTH_JWT_SECRET` / `AUTH_ADMIN_TOKEN` are the shipped dev defaults. |
| S4 | Same 401 for unknown vs bad API key | (by design) | Confirmed intentional — does not leak which half of a credential was wrong. |

## Residual risks / accepted (deployment-milestone items)

- **TLS in transit** — terminated at the ingress/gateway in production (NFR11); not applicable to the local
  Compose stack.
- **Secret storage** — production secrets come from a secret manager (the Terraform/K8s layer); the repo
  contains no real secrets (only `.example` templates), and CI runs with none.
- **HS256 shared-secret JWT** — acceptable while one party operates every service; migrating to RS256 + JWKS
  is isolated to `cbir_common.auth.jwt_contract` + the signer for when real external trust boundaries appear.
- **Dependency audit** — `pip-audit`/Dependabot is the recommended standing control; dependencies are
  version-pinned.

No unresolved critical or high findings.
