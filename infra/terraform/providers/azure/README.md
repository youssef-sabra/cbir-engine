# providers/azure/

**Status: reserved, not yet implemented.**

An Azure implementation of this project's infrastructure would live here, implementing the same contracts
defined in `infra/terraform/modules/{networking,cluster,data-services}/`:

| Contract module | Anticipated Azure resources |
|---|---|
| `networking` | `azurerm_virtual_network`, `azurerm_subnet` |
| `cluster` | `azurerm_kubernetes_cluster` with a default (CPU) node pool plus an `azurerm_kubernetes_cluster_node_pool` for GPU nodes (mirroring the taint/label pattern used in `providers/gcp/cluster/main.tf`) |
| `data-services` | `azurerm_postgresql_flexible_server` (`pgvector` enabled), `azurerm_redis_cache` |

This directory is created now (empty) specifically so that adding Azure support later is a "write a new
implementation behind an already-agreed contract" task — see `infra/README.md` for the full rationale.

No Azure credentials, subscription, or resources are required for local development or for the current CI
pipeline. This directory has no effect on the project until someone deliberately implements it and wires it
into a new `infra/terraform/environments/production-azure/` root module.
