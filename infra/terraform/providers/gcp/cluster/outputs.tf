# Satisfies infra/terraform/modules/cluster/outputs.tf (the contract).

output "cluster_endpoint" {
  description = "GKE cluster API server endpoint."
  value       = google_container_cluster.primary.endpoint
}

output "cluster_ca_certificate" {
  description = "Base64-encoded cluster CA certificate."
  value       = google_container_cluster.primary.master_auth[0].cluster_ca_certificate
  sensitive   = true
}

output "cpu_pool_name" {
  value = google_container_node_pool.cpu_pool.name
}

output "gpu_pool_name" {
  value = google_container_node_pool.gpu_pool.name
}
