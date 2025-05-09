variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "region" {
  description = "GCP Region"
  type        = string
  default     = "us-central1"
}

variable "zone" {
  description = "GCP Zone"
  type        = string
  default     = "us-central1-a"
}

# Main cluster node pool configuration
variable "node_pool_machine_type" {
  description = "Machine type for the main node pool"
  type        = string
  default     = "e2-standard-4"
}

variable "node_pool_min_count" {
  description = "Minimum number of nodes in the main node pool"
  type        = number
  default     = 1
}

variable "node_pool_max_count" {
  description = "Maximum number of nodes in the main node pool"
  type        = number
  default     = 3
}

# GPU node pool configuration
variable "gpu_node_count" {
  description = "Number of GPU nodes in the cluster"
  type        = number
  default     = 1
}

variable "gpu_node_machine_type" {
  description = "Machine type for GPU nodes"
  type        = string
  default     = "n1-standard-4"
}

variable "gpu_type" {
  description = "Type of GPU to use (e.g., nvidia-tesla-t4)"
  type        = string
  default     = "nvidia-tesla-t4"
}

variable "gpu_count_per_node" {
  description = "Number of GPUs per node"
  type        = number
  default     = 1
}

# KAI Scheduler configuration
variable "kai_scheduler_version" {
  description = "Version of KAI Scheduler to install"
  type        = string
  default     = "v0.5.0"
}

# Storage configuration
variable "artifact_store_bucket_name" {
  description = "Name for the GCS bucket used as artifact store (if empty, a name will be generated)"
  type        = string
  default     = ""
}

variable "bucket_versioning_enabled" {
  description = "Enable versioning for the GCS bucket"
  type        = bool
  default     = true
}