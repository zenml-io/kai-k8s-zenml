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

variable "existing_cluster_name" {
  description = "Name of the existing GKE cluster to use"
  type        = string
  default     = "zenml-kai-cluster"
}

variable "kubernetes_context" {
  description = "Kubernetes context to use"
  type        = string
  default     = "gke_zenml-core_us-central1-a_zenml-kai-cluster"
}

variable "kubernetes_namespace" {
  description = "Kubernetes namespace to use for deployments"
  type        = string
  default     = "default"
}

variable "stack_name" {
  description = "Name for the ZenML stack"
  type        = string
  default     = "kai-gcp-stack"
}

#---------------------------------------
# KAI Scheduler Configuration
#---------------------------------------

variable "gpu_fraction" {
  description = "Fraction of GPU resources to request (0.0-1.0)"
  type        = string
  default     = "0.5"
}

variable "kai_scheduler_queue" {
  description = "KAI Scheduler queue name"
  type        = string
  default     = "test"
}

variable "gpu_type" {
  description = "GPU type to target in node selector"
  type        = string
  default     = "nvidia-tesla-t4"
}

#---------------------------------------
# Resource Creation Configuration
#---------------------------------------

variable "create_resources" {
  description = "Whether to create GCS bucket and Container Registry resources (true) or use existing ones (false)"
  type        = bool
  default     = true
}

#---------------------------------------
# Storage Configuration
#---------------------------------------

variable "artifact_store_bucket_name" {
  description = "Name for the GCS bucket used as artifact store. Required when create_resources is false, otherwise a name will be auto-generated if not provided."
  type        = string
  default     = "zenml-core-zenml-artifacts"
}

variable "bucket_versioning_enabled" {
  description = "Enable versioning for the GCS bucket"
  type        = bool
  default     = true
}

variable "bucket_location" {
  description = "Location for the GCS bucket. Defaults to the same as the region variable."
  type        = string
  default     = ""
}

variable "bucket_storage_class" {
  description = "Storage class for the GCS bucket"
  type        = string
  default     = "STANDARD"
}

variable "bucket_retention_days" {
  description = "Number of days to retain artifacts in the bucket (0 to disable)"
  type        = number
  default     = 30
}

variable "bucket_uniform_access" {
  description = "Enable uniform bucket-level access"
  type        = bool
  default     = true
}

#---------------------------------------
# Container Registry Configuration
#---------------------------------------

variable "container_registry_uri" {
  description = "URI for the existing Container Registry. Required when create_resources is false, otherwise a URI will be auto-generated if not provided."
  type        = string
  default     = "gcr.io/zenml-core/zenml"
}

variable "container_registry_id" {
  description = "Repository ID for the Artifact Registry (only used when create_resources is true and container_registry_uri is not specified)"
  type        = string
  default     = ""
}

variable "container_registry_description" {
  description = "Description for the Artifact Registry repository"
  type        = string
  default     = "Docker repository for ZenML pipelines"
}

#---------------------------------------
# Service Account Configuration
#---------------------------------------

variable "create_service_account" {
  description = "Whether to create a new service account for GCP resources"
  type        = bool
  default     = false
}

variable "service_account_id" {
  description = "ID for the service account (only used when create_service_account is true)"
  type        = string
  default     = "zenml-service-account"
}

variable "generate_service_account_key" {
  description = "Whether to generate a new service account key when create_service_account is true"
  type        = bool
  default     = true
}

variable "output_service_account_key_file" {
  description = "Path to save the generated service account key (JSON). Leave empty to skip saving to a file."
  type        = string
  default     = ""
}

variable "service_account_key_file" {
  description = "Path to an existing service account key file (JSON)"
  type        = string
  default     = "keys/zenml-kai-scheduler.json"
}

variable "service_account_key_content" {
  description = "Raw content of the service account key (alternative to file path)"
  type        = string
  sensitive   = true
  default     = ""
}

variable "auth_method" {
  description = "Authentication method to use: service-account, implicit, or user-account"
  type        = string
  default     = "service-account"
  validation {
    condition     = contains(["service-account", "implicit", "user-account", "external-account", "oauth2-token", "impersonation"], var.auth_method)
    error_message = "auth_method must be one of: service-account, implicit, user-account, external-account, oauth2-token, impersonation"
  }
}

# Legacy variable - kept for backward compatibility
variable "gcp_service_account_json" {
  description = "GCP Service Account JSON key content (sensitive)"
  type        = string
  sensitive   = true
  default     = ""
}