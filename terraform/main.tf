terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0.0"
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

provider "zenml" {
  # Uses ZENML_SERVER_URL and ZENML_API_KEY environment variables
}

# Use data source instead of resource for existing GCS bucket
data "google_storage_bucket" "artifact_store" {
  name = var.artifact_store_bucket_name
}

# Create a service connector for GCP
resource "zenml_service_connector" "gcp_connector" {
  name           = "gcp-${var.stack_name}"
  type           = "gcp"
  resource_types = ["artifact-store", "container-registry", "orchestrator"]
  auth_method    = "service-account"

  configuration = {
    project_id = var.project_id
    location   = var.region
  }

  secrets = {
    service_account_json = jsondecode(file("keys/zenml-kai-scheduler.json")).private_key
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

  connector_id = zenml_service_connector.gcp_connector.id
}

# Register the GCP container registry component
resource "zenml_stack_component" "container_registry" {
  name   = "gcp-container-registry-${var.stack_name}"
  type   = "container_registry"
  flavor = "gcp"

  configuration = {
    uri = var.container_registry_uri
  }

  connector_id = zenml_service_connector.gcp_connector.id
}

# Register Kubernetes orchestrator with KAI Scheduler configuration
resource "zenml_stack_component" "k8s_orchestrator" {
  name   = "kai-kubernetes-${var.stack_name}"
  type   = "orchestrator"
  flavor = "kubernetes"

  configuration = {
    kubernetes_context   = var.kubernetes_context
    kubernetes_namespace = "zenml"

    # KAI Scheduler configuration encoded as a JSON string
    pod_settings = jsonencode({
      scheduler_name = "kai-scheduler"
      labels = {
        "runai/queue" = "test"
      }
      resources = {
        limits = {
          "nvidia.com/gpu" = "1"
        }
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

  connector_id = zenml_service_connector.gcp_connector.id
}

# Create a ZenML stack with the registered components
resource "zenml_stack" "kai_stack" {
  name = var.stack_name

  components = {
    orchestrator       = zenml_stack_component.k8s_orchestrator.id
    artifact_store     = zenml_stack_component.artifact_store.id
    container_registry = zenml_stack_component.container_registry.id
  }
}
