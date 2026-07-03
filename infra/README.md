# infra/

**Nothing in this directory is executed during local development, and nothing here requires a cloud
account, credentials, or billing to work on this project day to day.** It exists to keep the project
*prepared* for cloud deployment, deferred to a future milestone (see `docs/MILESTONES.md`).

## Design: interface / implementation split

To avoid vendor lock-in without inventing new tooling, the Terraform layer is split into three parts:

```
infra/terraform/
├── modules/            <- THE CONTRACT: variables + outputs only, no resources, no provider blocks
│   ├── networking/
│   ├── cluster/
│   └── data-services/
├── providers/          <- THE IMPLEMENTATIONS: one per cloud, each satisfying the contract above
│   ├── gcp/             (implemented — reference production target)
│   ├── aws/              (reserved — not yet implemented)
│   └── azure/            (reserved — not yet implemented)
└── environments/       <- THE WIRING: picks one provider implementation and deploys it
    └── production-gcp/
```

**Important honesty note:** Terraform itself has no formal "interface satisfies contract" enforcement
mechanism. The files under `modules/` are a *documented contract* — the exact set of input variables and
output values every provider implementation must expose — copied and filled in by each `providers/<cloud>/`
directory. Nothing prevents a provider implementation from drifting from that contract; it's a discipline
enforced by code review and by keeping `modules/*/variables.tf` and `modules/*/outputs.tf` as the always-
consulted reference, not by the tool itself. This is called out explicitly rather than overclaiming
automatic portability — see `docs/CLEAN_ARCHITECTURE.md` for the equivalent, and more rigorously enforced,
pattern applied inside application code (Clean Architecture's dependency rule *is* enforced by import
discipline within a codebase in a way this Terraform pattern only approximates at the infra level).

## Why GCP is implemented first

Per `docs/TECH_STACK.md`, GCP is the reference production deployment target (GPU cost, startup credit
ceiling for AI-first products, and GKE Autopilot's lower operational overhead for a small team). `aws/` and
`azure/` are created as empty, documented sibling directories now specifically so adding either later is a
"write a new implementation behind an already-agreed contract" task, not a restructuring conversation.

## What "prepared but not executed" means concretely

- No `terraform init`/`plan`/`apply` runs in CI (see `.github/workflows/ci.yml` — there is no deploy job).
- No cloud credentials are stored or referenced anywhere in this repository.
- `infra/terraform/environments/production-gcp/terraform.tfvars.example` documents the inputs a real
  deployment would need, but the real `terraform.tfvars` is gitignored and only created when someone
  deliberately decides to deploy.
- The Kubernetes manifests under `infra/kubernetes/` describe what would run in a cluster; they are never
  applied to any cluster during Milestone 1.

## Kubernetes layout

```
infra/kubernetes/
├── base/               <- Vanilla, cloud-agnostic Kubernetes manifests
└── overlays/
    ├── gcp/             (implemented — GKE-specific patches: ingress class, storage class)
    ├── aws/              (reserved)
    └── azure/            (reserved)
```

Kubernetes manifests are already close to cloud-agnostic by construction (they're just Kubernetes API
objects); the overlays isolate the genuinely cloud-specific pieces (ingress controller class, storage class
names) using the Kustomize base/overlay pattern.
