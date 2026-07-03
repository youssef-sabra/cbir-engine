# -----------------------------------------------------------------------------
# CONTRACT: networking module.
#
# Every implementation under infra/terraform/providers/<cloud>/networking/
# must accept these inputs. This file defines no resources and no provider
# block on purpose -- it is documentation of the interface, not executable
# infrastructure. See infra/README.md for why.
# -----------------------------------------------------------------------------

variable "environment_name" {
  description = "Logical environment name, e.g. \"production\". Used for resource naming/tagging."
  type        = string
}

variable "region" {
  description = "Cloud region to provision networking resources in."
  type        = string
}

variable "vpc_cidr_range" {
  description = "CIDR range for the primary VPC/virtual network."
  type        = string
  default     = "10.0.0.0/16"
}

variable "subnet_cidr_range" {
  description = "CIDR range for the primary subnet used by the Kubernetes cluster."
  type        = string
  default     = "10.0.0.0/20"
}
