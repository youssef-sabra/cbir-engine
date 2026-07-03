# providers/aws/

**Status: reserved, not yet implemented.**

An AWS implementation of this project's infrastructure would live here, implementing the same contracts
defined in `infra/terraform/modules/{networking,cluster,data-services}/`:

| Contract module | Anticipated AWS resources |
|---|---|
| `networking` | `aws_vpc`, `aws_subnet` |
| `cluster` | `aws_eks_cluster` with two `aws_eks_node_group` resources (CPU and GPU, mirroring the taint/label pattern used in `providers/gcp/cluster/main.tf`) |
| `data-services` | `aws_db_instance` (RDS for PostgreSQL, `pgvector` enabled), `aws_elasticache_cluster` (Redis) |

This directory is created now (empty) specifically so that adding AWS support later is a "write a new
implementation behind an already-agreed contract" task — see `infra/README.md` for the full rationale.

No AWS credentials, account, or resources are required for local development or for the current CI
pipeline. This directory has no effect on the project until someone deliberately implements it and wires it
into a new `infra/terraform/environments/production-aws/` root module.
