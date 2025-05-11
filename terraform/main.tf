terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0.0"
    }
    zenml = {
      source  = "zenml-io/zenml"
      version = "~> 2.0.2"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
  zone    = var.zone
}

provider "zenml" {
  # Uses ZENML_SERVER_URL and ZENML_API_KEY environment variables
}

# Use data source instead of resource for existing GCS bucket
data "google_storage_bucket" "artifact_store" {
  name = var.artifact_store_bucket_name
}

# Create a service connector for GCS
resource "zenml_service_connector" "gcs" {
  name          = "gcp-${var.stack_name}-gcs"
  type          = "gcp"
  auth_method   = "service-account"
  resource_type = "gcs-bucket"
  resource_id   = var.artifact_store_bucket_name
  configuration = {
    project_id           = var.project_id
    service_account_json = file("keys/zenml-kai-scheduler.json")
  }

}

# Create a service connector for GKE
resource "zenml_service_connector" "gke" {
  name          = "gcp-${var.stack_name}-gke"
  type          = "gcp"
  auth_method   = "service-account"
  resource_type = "kubernetes-cluster"
  resource_id   = var.existing_cluster_name
  configuration = {
    project_id           = var.project_id
    service_account_json = file("keys/zenml-kai-scheduler.json")
  }

}

# Create a service connector for GCR
resource "zenml_service_connector" "gcr" {
  name          = "gcp-${var.stack_name}-gcr"
  type          = "gcp"
  auth_method   = "service-account"
  resource_type = "docker-registry"
  resource_id   = var.container_registry_uri
  configuration = {
    project_id           = var.project_id
    service_account_json = file("keys/zenml-kai-scheduler.json")
  }

}

# Register the GCP artifact store component
resource "zenml_stack_component" "artifact_store" {
  name   = "gcp-artifact-store-${var.stack_name}"
  type   = "artifact_store"
  flavor = "gcp"

  configuration = {
    path = "gs://${data.google_storage_bucket.artifact_store.name}"
  }

  connector_id = zenml_service_connector.gcs.id
}

# Register the GCP container registry component
resource "zenml_stack_component" "container_registry" {
  name   = "gcp-container-registry-${var.stack_name}"
  type   = "container_registry"
  flavor = "gcp"

  configuration = {
    uri = var.container_registry_uri
  }

  connector_id = zenml_service_connector.gcr.id
}


# Register a KAI Scheduler orchestrator with fractional GPU support
resource "zenml_stack_component" "kai_gpu_sharing_orchestrator" {
  name   = "kai-gpu-sharing-${var.stack_name}"
  type   = "orchestrator"
  flavor = "kubernetes"

  configuration = {
    kubernetes_context   = var.kubernetes_context
    kubernetes_namespace = "kai-test"

    # KAI Scheduler configuration with GPU sharing (for reference)
    pod_settings = jsonencode({
      scheduler_name = "kai-scheduler"
      annotations = {
        "gpu-fraction" = "0.5" # Request 50% of GPU resources
      }
      tolerations = [
        {
          key      = "nvidia.com/gpu"
          operator = "Equal"
          value    = "present"
          effect   = "NoSchedule"
        }
      ]
    })
  }

  connector_id = zenml_service_connector.gke.id
}


# Create a second ZenML stack with the GPU sharing orchestrator
resource "zenml_stack" "kai_stack" {
  name = var.stack_name

  components = {
    orchestrator       = zenml_stack_component.kai_gpu_sharing_orchestrator.id
    artifact_store     = zenml_stack_component.artifact_store.id
    container_registry = zenml_stack_component.container_registry.id
  }
}
