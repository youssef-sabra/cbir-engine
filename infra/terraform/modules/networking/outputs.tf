# -----------------------------------------------------------------------------
# CONTRACT: networking module outputs.
#
# Every implementation under infra/terraform/providers/<cloud>/networking/
# must expose these outputs, so infra/terraform/environments/* and the
# cluster module contract can consume networking resources identically
# regardless of which cloud actually implements them.
# -----------------------------------------------------------------------------

output "network_id" {
  description = "Identifier of the provisioned VPC/virtual network, for consumption by the cluster module."
  value       = null # Overridden by each provider implementation.
}

output "subnet_id" {
  description = "Identifier of the primary subnet, for consumption by the cluster module."
  value       = null # Overridden by each provider implementation.
}
