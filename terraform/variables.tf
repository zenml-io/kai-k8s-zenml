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

variable "stack_name" {
  description = "Name for the ZenML stack"
  type        = string
  default     = "kai-gcp-stack"
}

# Storage configuration
variable "artifact_store_bucket_name" {
  description = "Name for the GCS bucket used as artifact store"
  type        = string
  default     = "zenml-core-zenml-artifacts"
}

variable "bucket_versioning_enabled" {
  description = "Enable versioning for the GCS bucket"
  type        = bool
  default     = true
}

variable "container_registry_uri" {
  description = "URI for the GCP Container Registry"
  type        = string
  default     = "gcr.io/zenml-core/zenml"
}

variable "gcp_service_account_json" {
  description = "GCP Service Account JSON key content (sensitive)"
  type        = string
  sensitive   = true
  default     = ""
}