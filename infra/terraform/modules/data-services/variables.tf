# -----------------------------------------------------------------------------
# CONTRACT: data-services module.
#
# RESERVED -- unpopulated until Milestone 3 (managed PostgreSQL/Redis) and
# Milestone 6 (managed/self-hosted vector database scale-out). This file
# exists now purely to reserve the location in the folder structure, per the
# same pattern as infra/ci/quality-gates/ (reserved for Milestone 9).
#
# Anticipated contract, subject to change once Milestone 3/6 are designed
# in detail:
# -----------------------------------------------------------------------------

variable "environment_name" {
  description = "Logical environment name, e.g. \"production\"."
  type        = string
}

variable "region" {
  description = "Cloud region to provision managed data services in."
  type        = string
}

variable "network_id" {
  description = "Identifier of the VPC/virtual network to attach managed data services to."
  type        = string
}
