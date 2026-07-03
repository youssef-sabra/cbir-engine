# Satisfies infra/terraform/modules/networking/outputs.tf (the contract).

output "network_id" {
  description = "Self-link of the provisioned VPC."
  value       = google_compute_network.vpc.id
}

output "subnet_id" {
  description = "Self-link of the provisioned subnet."
  value       = google_compute_subnetwork.subnet.id
}
