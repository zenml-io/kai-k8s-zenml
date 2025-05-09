terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0.0"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.23.0"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.11.0"
    }
    zenml = {
      source  = "zenml-io/zenml"
      version = "~> 1.0.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
  zone    = var.zone
}

# Configure kubectl provider for accessing the existing cluster
data "google_client_config" "provider" {}
data "google_container_cluster" "existing_cluster" {
  name     = var.existing_cluster_name
  location = var.zone
}

provider "kubernetes" {
  host  = "https://${data.google_container_cluster.existing_cluster.endpoint}"
  token = data.google_client_config.provider.access_token
  cluster_ca_certificate = base64decode(
    data.google_container_cluster.existing_cluster.master_auth[0].cluster_ca_certificate,
  )
}

provider "helm" {
  kubernetes {
    host  = "https://${data.google_container_cluster.existing_cluster.endpoint}"
    token = data.google_client_config.provider.access_token
    cluster_ca_certificate = base64decode(
      data.google_container_cluster.existing_cluster.master_auth[0].cluster_ca_certificate,
    )
  }
}

provider "zenml" {
  # Credentials are provided via environment variables:
  # ZENML_API_KEY and ZENML_SERVER_URL
}

# Create GCS bucket for artifact storage if it doesn't exist yet
resource "google_storage_bucket" "artifact_store" {
  name          = var.artifact_store_bucket_name
  location      = var.region
  force_destroy = true

  versioning {
    enabled = var.bucket_versioning_enabled
  }
}

# Create ZenML namespace if it doesn't exist yet
resource "kubernetes_namespace" "zenml" {
  count = var.create_zenml_namespace ? 1 : 0
  
  metadata {
    name = "zenml"
  }
}

# Register and configure stack with ZenML
resource "zenml_stack_component" "kubernetes_orchestrator" {
  name        = "${var.stack_name}-kubernetes"
  type        = "orchestrator"
  flavor      = "kubernetes"
  
  configuration = jsonencode({
    kubernetes_context     = var.kubernetes_context
    kubernetes_namespace   = "zenml"
    synchronous            = true
  })
}

resource "zenml_stack_component" "gcp_artifact_store" {
  name        = "${var.stack_name}-artifact-store"
  type        = "artifact_store"
  flavor      = "gcp"
  
  configuration = jsonencode({
    path = "gs://${google_storage_bucket.artifact_store.name}"
  })
}

resource "zenml_stack_component" "gcp_container_registry" {
  name        = "${var.stack_name}-container-registry"
  type        = "container_registry"
  flavor      = "gcp"
  
  configuration = jsonencode({
    uri = var.container_registry_uri
  })
}

resource "zenml_stack" "kai_stack" {
  name        = var.stack_name
  orchestrator = zenml_stack_component.kubernetes_orchestrator.id
  artifact_store = zenml_stack_component.gcp_artifact_store.id
  container_registry = zenml_stack_component.gcp_container_registry.id

  depends_on = [
    google_storage_bucket.artifact_store,
    kubernetes_namespace.zenml
  ]
}