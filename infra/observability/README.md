# infra/observability/ — Monitoring & Observability (Milestone 10)

Every FastAPI service is instrumented by one call — `cbir_common.observability.instrument(app, name)` —
which adds:

- **Prometheus metrics** at `GET /metrics`: `http_requests_total{service,method,path,status}`,
  `http_request_duration_seconds` (histogram, buckets tuned to the NFR latency targets), and
  `http_requests_in_progress`. The `path` label is the route *template* (`/v1/items/{item_id}`), so
  cardinality stays bounded.
- **Request-id / trace correlation**: an `X-Request-ID` is generated (or propagated if supplied) and
  echoed on the response, giving a correlation id across logs and downstream calls.

The **ingestion-worker** (no HTTP API) exposes metrics on `:9100/metrics`:
`ingestion_jobs_total{result}`, `ingestion_job_duration_seconds`, and `ingestion_queue_depth{queue}`
(main + dead-letter), so backlog and DLQ growth are alertable.

Structured JSON logging (`cbir_common.structured_logging`) is shared by every service; raw image bytes
and credentials are never logged (NFR14).

## Stack

- **Prometheus** (`:9090`) — scrapes all services + the worker (`prometheus/prometheus.yml`) and evaluates
  NFR-tied alert rules (`prometheus/alerts.yml`: P95 latency breach, 5xx rate, DLQ non-empty, backlog high,
  target down).
- **Grafana** (`:3000`, default admin/admin) — auto-provisioned Prometheus datasource and the
  "CBIR Engine — Overview" dashboard (request rate, P95 latency, error rate, ingestion throughput, queue
  depth).

Both start with `docker compose up`. Open Grafana at http://localhost:3000 and Prometheus targets at
http://localhost:9090/targets.

## Production note

Prometheus + Grafana here are the local reference. In production these map to a managed Prometheus/Grafana
(or Cloud Monitoring) with the same scrape targets and dashboards; OpenTelemetry tracing to Tempo/Jaeger is
the documented next increment (the request-id middleware is the correlation seam it builds on).
