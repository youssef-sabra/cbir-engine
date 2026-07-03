# Mirrors infra/terraform/modules/cluster/variables.tf (the contract).

variable "environment_name" {
  description = "Logical environment name, e.g. \"production\"."
  type        = string
}

variable "region" {
  description = "GCP region for the GKE cluster."
  type        = string
}

variable "network_id" {
  description = "Self-link of the VPC (from the networking module's output)."
  type        = string
}

variable "subnet_id" {
  description = "Self-link of the subnet (from the networking module's output)."
  type        = string
}

variable "cpu_pool_machine_type" {
  description = "GCE machine type for the CPU node pool."
  type        = string
  default     = "e2-standard-4"
}

variable "cpu_pool_min_nodes" {
  type    = number
  default = 1
}

variable "cpu_pool_max_nodes" {
  type    = number
  default = 5
}

variable "gpu_pool_machine_type" {
  description = "GCE machine type for the GPU node pool (A2 family for A100 GPUs)."
  type        = string
  default     = "a2-highgpu-1g"
}

variable "gpu_pool_accelerator_type" {
  description = "GPU accelerator type."
  type        = string
  default     = "nvidia-tesla-a100"
}

variable "gpu_pool_min_nodes" {
  description = "Defaults to 0: no GPU nodes (no GPU cost) until the AI Service schedules a workload."
  type        = number
  default     = 0
}

variable "gpu_pool_max_nodes" {
  type    = number
  default = 3
}
