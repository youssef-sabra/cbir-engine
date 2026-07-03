# -----------------------------------------------------------------------------
# GCP implementation of the cluster module contract
# (see infra/terraform/modules/cluster/{variables,outputs}.tf).
#
# Implements GKE Autopilot's manually-managed-node-pool equivalent via
# standard GKE with two explicitly separated node pools -- CPU and GPU --
# matching the topology decided in docs/ARCHITECTURE.md Section 10 and
# docs/MILESTONES.md Milestone 1.
#
# NOT executed as part of Milestone 1 or CI. See infra/terraform/providers/gcp/networking/main.tf
# for the same disclaimer.
# -----------------------------------------------------------------------------

terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

resource "google_container_cluster" "primary" {
  name     = "cbir-${var.environment_name}"
  location = var.region

  network    = var.network_id
  subnetwork = var.subnet_id

  # We manage node pools explicitly below rather than using the default pool,
  # so the default pool is removed immediately after cluster creation.
  remove_default_node_pool = true
  initial_node_count       = 1

  networking_mode = "VPC_NATIVE"
  ip_allocation_policy {
    cluster_secondary_range_name  = "pods"
    services_secondary_range_name = "services"
  }
}

# ---------------------------------------------------------------------------
# CPU node pool: FastAPI services, background workers, admin service.
# ---------------------------------------------------------------------------
resource "google_container_node_pool" "cpu_pool" {
  name     = "cpu-pool"
  location = var.region
  cluster  = google_container_cluster.primary.name

  autoscaling {
    min_node_count = var.cpu_pool_min_nodes
    max_node_count = var.cpu_pool_max_nodes
  }

  node_config {
    machine_type = var.cpu_pool_machine_type
    labels = {
      "cbir.dev/node-pool" = "cpu"
    }
  }
}

# ---------------------------------------------------------------------------
# GPU node pool: AI Service (embedding + reranking), introduced Milestone 5.
# Tainted so that only workloads with a matching toleration are scheduled
# here -- prevents ordinary API pods from accidentally landing on (expensive)
# GPU nodes. Min node count defaults to 0 (see modules/cluster/variables.tf)
# so no GPU cost is incurred until the AI Service actually exists and
# schedules a workload.
# ---------------------------------------------------------------------------
resource "google_container_node_pool" "gpu_pool" {
  name     = "gpu-pool"
  location = var.region
  cluster  = google_container_cluster.primary.name

  autoscaling {
    min_node_count = var.gpu_pool_min_nodes
    max_node_count = var.gpu_pool_max_nodes
  }

  node_config {
    machine_type = var.gpu_pool_machine_type

    guest_accelerator {
      type  = var.gpu_pool_accelerator_type
      count = 1
    }

    labels = {
      "cbir.dev/node-pool" = "gpu"
    }

    taint {
      key    = "cbir.dev/gpu"
      value  = "true"
      effect = "NO_SCHEDULE"
    }
  }
}
