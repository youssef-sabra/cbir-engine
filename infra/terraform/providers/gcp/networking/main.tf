# -----------------------------------------------------------------------------
# GCP implementation of the networking module contract
# (see infra/terraform/modules/networking/{variables,outputs}.tf).
#
# NOT executed as part of Milestone 1 or CI. Reference implementation only,
# wired up by infra/terraform/environments/production-gcp when a real
# deployment is deliberately triggered in a future milestone.
# -----------------------------------------------------------------------------

terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

resource "google_compute_network" "vpc" {
  name                    = "cbir-${var.environment_name}-vpc"
  auto_create_subnetworks = false
}

resource "google_compute_subnetwork" "subnet" {
  name          = "cbir-${var.environment_name}-subnet"
  ip_cidr_range = var.subnet_cidr_range
  region        = var.region
  network       = google_compute_network.vpc.id

  # Secondary ranges for GKE pod/service IPs -- required for VPC-native
  # (alias IP) clusters, which is the recommended GKE networking mode.
  secondary_ip_range {
    range_name    = "pods"
    ip_cidr_range = "10.4.0.0/14"
  }
  secondary_ip_range {
    range_name    = "services"
    ip_cidr_range = "10.8.0.0/20"
  }
}
