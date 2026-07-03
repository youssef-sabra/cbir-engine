# -----------------------------------------------------------------------------
# production-gcp environment.
#
# Wires the GCP provider implementations (providers/gcp/networking,
# providers/gcp/cluster) into a deployable environment. This is the root
# module someone would actually run `terraform init/plan/apply` against --
# but NOT during Milestone 1, and NOT as part of CI. See infra/README.md.
#
# A future infra/terraform/environments/production-aws/ or
# production-azure/ would follow this exact same pattern: wire the
# corresponding provider's implementations together, with zero changes
# required to infra/terraform/modules/ (the contract).
# -----------------------------------------------------------------------------

terraform {
  required_version = ">= 1.7"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }

  # Intentionally left as local state for now. Before any real `terraform
  # apply` is run against this environment, this should be switched to a
  # remote backend (e.g. a GCS bucket) so state isn't only on one machine --
  # tracked as a task for the future deployment milestone, not Milestone 1.
  # backend "gcs" {
  #   bucket = "cbir-engine-tfstate"
  #   prefix = "production-gcp"
  # }
}

provider "google" {
  project = var.gcp_project_id
  region  = var.region
}

module "networking" {
  source = "../../providers/gcp/networking"

  environment_name  = var.environment_name
  region            = var.region
  vpc_cidr_range    = var.vpc_cidr_range
  subnet_cidr_range = var.subnet_cidr_range
}

module "cluster" {
  source = "../../providers/gcp/cluster"

  environment_name = var.environment_name
  region            = var.region
  network_id        = module.networking.network_id
  subnet_id         = module.networking.subnet_id

  cpu_pool_machine_type    = var.cpu_pool_machine_type
  cpu_pool_min_nodes       = var.cpu_pool_min_nodes
  cpu_pool_max_nodes       = var.cpu_pool_max_nodes
  gpu_pool_machine_type    = var.gpu_pool_machine_type
  gpu_pool_accelerator_type = var.gpu_pool_accelerator_type
  gpu_pool_min_nodes       = var.gpu_pool_min_nodes
  gpu_pool_max_nodes       = var.gpu_pool_max_nodes
}

# NOTE: module "data_services" intentionally omitted -- reserved until
# Milestone 3/6. See infra/terraform/providers/gcp/data-services/README.md.
