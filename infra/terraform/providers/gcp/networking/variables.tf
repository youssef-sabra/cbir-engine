# Mirrors infra/terraform/modules/networking/variables.tf (the contract).
# Kept as a literal copy here -- see infra/README.md for why Terraform does
# not enforce this automatically and why that's an accepted tradeoff.

variable "environment_name" {
  description = "Logical environment name, e.g. \"production\"."
  type        = string
}

variable "region" {
  description = "GCP region, e.g. \"us-central1\"."
  type        = string
}

variable "vpc_cidr_range" {
  description = "CIDR range for the VPC (informational; GCP auto-mode-off VPCs don't require a single range, but kept for contract parity with other clouds)."
  type        = string
  default     = "10.0.0.0/16"
}

variable "subnet_cidr_range" {
  description = "CIDR range for the primary GKE subnet."
  type        = string
  default     = "10.0.0.0/20"
}
