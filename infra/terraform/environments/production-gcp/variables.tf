variable "gcp_project_id" {
  description = "GCP project ID to deploy into."
  type        = string
}

variable "environment_name" {
  description = "Logical environment name."
  type        = string
  default     = "production"
}

variable "region" {
  description = "GCP region."
  type        = string
  default     = "us-central1"
}

variable "vpc_cidr_range" {
  type    = string
  default = "10.0.0.0/16"
}

variable "subnet_cidr_range" {
  type    = string
  default = "10.0.0.0/20"
}

variable "cpu_pool_machine_type" {
  type    = string
  default = "e2-standard-4"
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
  type    = string
  default = "a2-highgpu-1g"
}

variable "gpu_pool_accelerator_type" {
  type    = string
  default = "nvidia-tesla-a100"
}

variable "gpu_pool_min_nodes" {
  description = "Defaults to 0: no GPU spend until the AI Service (Milestone 5) actually schedules a workload."
  type        = number
  default     = 0
}

variable "gpu_pool_max_nodes" {
  type    = number
  default = 3
}
