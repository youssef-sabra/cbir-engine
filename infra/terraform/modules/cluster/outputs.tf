# -----------------------------------------------------------------------------
# CONTRACT: cluster module outputs.
# Documentation-only file -- see infra/README.md.
# -----------------------------------------------------------------------------

output "cluster_endpoint" {
  description = "API server endpoint of the provisioned Kubernetes cluster."
  value       = null # Overridden by each provider implementation.
}

output "cluster_ca_certificate" {
  description = "Base64-encoded cluster CA certificate, for kubeconfig generation."
  value       = null # Overridden by each provider implementation.
  sensitive   = true
}

output "cpu_pool_name" {
  description = "Name of the CPU node pool, for use in Kubernetes node selectors/affinity rules."
  value       = null # Overridden by each provider implementation.
}

output "gpu_pool_name" {
  description = "Name of the GPU node pool, for use in Kubernetes node selectors/affinity rules and taints."
  value       = null # Overridden by each provider implementation.
}
