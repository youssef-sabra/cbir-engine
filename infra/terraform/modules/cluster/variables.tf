# -----------------------------------------------------------------------------
# CONTRACT: cluster module.
#
# Every implementation under infra/terraform/providers/<cloud>/cluster/
# must accept these inputs. Documentation-only file -- see infra/README.md.
# -----------------------------------------------------------------------------

variable "environment_name" {
  description = "Logical environment name, e.g. \"production\". Used for resource naming/tagging."
  type        = string
}

variable "region" {
  description = "Cloud region to provision the Kubernetes cluster in."
  type        = string
}

variable "network_id" {
  description = "Identifier of the VPC/virtual network to attach the cluster to (from the networking module's output)."
  type        = string
}

variable "subnet_id" {
  description = "Identifier of the subnet to attach the cluster's nodes to (from the networking module's output)."
  type        = string
}

variable "cpu_pool_machine_type" {
  description = "Machine/instance type for the CPU node pool (runs API services, workers, admin service)."
  type        = string
  default     = "e2-standard-4"
}

variable "cpu_pool_min_nodes" {
  description = "Minimum node count for the CPU pool autoscaler."
  type        = number
  default     = 1
}

variable "cpu_pool_max_nodes" {
  description = "Maximum node count for the CPU pool autoscaler."
  type        = number
  default     = 5
}

variable "gpu_pool_machine_type" {
  description = "Machine/instance type for the GPU node pool (runs the AI Service: embedding + reranking)."
  type        = string
  default     = "a2-highgpu-1g"
}

variable "gpu_pool_accelerator_type" {
  description = "GPU accelerator type attached to GPU pool nodes."
  type        = string
  default     = "nvidia-tesla-a100"
}

variable "gpu_pool_min_nodes" {
  description = "Minimum node count for the GPU pool autoscaler. Defaults to 0 so no GPU cost is incurred until the AI Service (Milestone 5) actually schedules a workload."
  type        = number
  default     = 0
}

variable "gpu_pool_max_nodes" {
  description = "Maximum node count for the GPU pool autoscaler."
  type        = number
  default     = 3
}
