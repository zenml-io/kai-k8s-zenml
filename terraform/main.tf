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
    random = {
      source  = "hashicorp/random"
      version = "~> 3.5.1"
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

locals {
  # Determine the bucket location based on region if not specified
  bucket_location = var.bucket_location != "" ? var.bucket_location : var.region
  
  # Service account authentication configuration with enhanced fallback logic
  service_account_json = (
    # First, check if we should use a newly generated key
    (var.create_service_account && var.generate_service_account_key && length(google_service_account_key.zenml_sa_key) > 0) ? 
      base64decode(google_service_account_key.zenml_sa_key[0].private_key) : (
      # Otherwise, check if content was provided directly
      var.service_account_key_content != "" ? var.service_account_key_content : (
        # Next, try to use the specified key file
        var.service_account_key_file != "" ? file(var.service_account_key_file) : (
          # Finally, try the legacy variable
          var.gcp_service_account_json != "" ? var.gcp_service_account_json : ""
        )
      )
    )
  )
  
  # Service account email for outputs
  service_account_email = var.create_service_account ? (
    length(google_service_account.zenml_service_account) > 0 ? 
      google_service_account.zenml_service_account[0].email : ""
  ) : ""
  
  # Container registry configuration
  container_registry_id = var.container_registry_id != "" ? var.container_registry_id : "zenml-repository-${random_id.suffix.hex}"
  
  # Determine the container registry URI format based on creation flag
  # If creating new registry, use Artifact Registry format, otherwise use the provided URI
  container_registry_uri = var.create_resources ? (
    # Format for Artifact Registry: REGION-docker.pkg.dev/PROJECT-ID/REPOSITORY-ID
    "${var.region}-docker.pkg.dev/${var.project_id}/${local.container_registry_id}"
  ) : var.container_registry_uri
}

# Use a data source for an existing GCS bucket when create_resources is false
data "google_storage_bucket" "artifact_store" {
  count = var.create_resources ? 0 : 1
  name  = var.artifact_store_bucket_name
}

# Generate a random suffix for resource names
resource "random_id" "suffix" {
  byte_length = 4
}

# Bucket name with generated suffix if not provided
locals {
  generated_bucket_name = "zenml-artifacts-${var.project_id}-${random_id.suffix.hex}"
  # Use the provided name or generate one if creating a new bucket
  bucket_name = var.create_resources ? (
    var.artifact_store_bucket_name != "zenml-core-zenml-artifacts" ? var.artifact_store_bucket_name : local.generated_bucket_name
  ) : var.artifact_store_bucket_name
}

# Create a new GCS bucket for artifact store when create_resources is true
resource "google_storage_bucket" "artifact_store" {
  count = var.create_resources ? 1 : 0
  
  name          = local.bucket_name
  location      = local.bucket_location
  storage_class = var.bucket_storage_class
  project       = var.project_id
  
  # Enable versioning based on configuration
  versioning {
    enabled = var.bucket_versioning_enabled
  }
  
  # Configure uniform bucket-level access
  uniform_bucket_level_access = var.bucket_uniform_access
  
  # Add lifecycle rules if retention days is specified
  dynamic "lifecycle_rule" {
    for_each = var.bucket_retention_days > 0 ? [1] : []
    content {
      condition {
        age = var.bucket_retention_days
      }
      action {
        type = "Delete"
      }
    }
  }
  
  # Add standard labels
  labels = {
    managed_by = "terraform"
    purpose    = "zenml-artifacts"
  }
}

# Create a Google Artifact Registry repository for container images when create_resources is true
resource "google_artifact_registry_repository" "container_registry" {
  count = var.create_resources ? 1 : 0
  
  provider = google
  
  location      = var.region
  repository_id = local.container_registry_id
  description   = var.container_registry_description
  format        = "DOCKER"
  project       = var.project_id
  
  # Add labels for better organization
  labels = {
    managed_by = "terraform"
    purpose    = "zenml-containers"
  }
}

# Create a dedicated service account for ZenML when create_service_account is true
resource "google_service_account" "zenml_service_account" {
  count = var.create_service_account ? 1 : 0
  
  account_id   = "${var.service_account_id}-${random_id.suffix.hex}"
  display_name = "ZenML Service Account"
  description  = "Service account for ZenML operations (GCS, Artifact Registry, GKE)"
  project      = var.project_id
}

# Grant IAM permissions to the ZenML service account when create_service_account is true

# 1. Grant GCS bucket permissions (for artifact store)
# Use storage.admin for complete access (includes buckets.get, buckets.update, objects.*)
resource "google_storage_bucket_iam_member" "artifact_store_admin" {
  count = var.create_service_account && var.create_resources ? 1 : 0
  
  bucket = google_storage_bucket.artifact_store[0].name
  role   = "roles/storage.admin"
  member = "serviceAccount:${google_service_account.zenml_service_account[0].email}"
  
  # Add explicit dependency to ensure service account is fully created
  depends_on = [
    google_service_account.zenml_service_account,
    google_service_account_key.zenml_sa_key
  ]
}

# 2. Grant permissions for using an existing GCS bucket
# Use storage.admin for complete access
resource "google_storage_bucket_iam_member" "existing_artifact_store_admin" {
  count = var.create_service_account && !var.create_resources ? 1 : 0
  
  bucket = var.artifact_store_bucket_name
  role   = "roles/storage.admin"
  member = "serviceAccount:${google_service_account.zenml_service_account[0].email}"
  
  # Add explicit dependency to ensure service account is fully created
  depends_on = [
    google_service_account.zenml_service_account,
    google_service_account_key.zenml_sa_key
  ]
}

# 3. Grant Artifact Registry permissions (for container registry)
# Use artifactregistry.admin for complete access (includes repositories.*, formats.*, packages.*, versions.*, tags.*)
resource "google_artifact_registry_repository_iam_member" "container_registry_admin" {
  count = var.create_service_account && var.create_resources ? 1 : 0
  
  provider   = google
  location   = google_artifact_registry_repository.container_registry[0].location
  repository = google_artifact_registry_repository.container_registry[0].name
  role       = "roles/artifactregistry.admin"
  member     = "serviceAccount:${google_service_account.zenml_service_account[0].email}"
  
  # Add explicit dependency to ensure service account is fully created
  depends_on = [
    google_service_account.zenml_service_account,
    google_service_account_key.zenml_sa_key
  ]
}

# 4. Grant GKE access permissions
resource "google_project_iam_member" "gke_developer" {
  count = var.create_service_account ? 1 : 0
  
  project = var.project_id
  role    = "roles/container.developer"
  member  = "serviceAccount:${google_service_account.zenml_service_account[0].email}"
  
  # Add explicit dependency to ensure service account is fully created
  depends_on = [google_service_account.zenml_service_account]
}

# 5. Grant storage permissions for the project
resource "google_project_iam_member" "storage_admin" {
  count = var.create_service_account ? 1 : 0
  
  project = var.project_id
  role    = "roles/storage.admin"
  member  = "serviceAccount:${google_service_account.zenml_service_account[0].email}"
  
  # Add explicit dependency to ensure service account is fully created
  depends_on = [google_service_account.zenml_service_account]
}

# 6. Grant Artifact Registry permissions for the project
resource "google_project_iam_member" "artifactregistry_admin" {
  count = var.create_service_account ? 1 : 0
  
  project = var.project_id
  role    = "roles/artifactregistry.admin"
  member  = "serviceAccount:${google_service_account.zenml_service_account[0].email}"
  
  # Add explicit dependency to ensure service account is fully created
  depends_on = [google_service_account.zenml_service_account]
}

# Create service account key when create_service_account is true and key creation is enabled
resource "google_service_account_key" "zenml_sa_key" {
  count = var.create_service_account && var.generate_service_account_key ? 1 : 0
  
  service_account_id = google_service_account.zenml_service_account[0].name
  
  # We can't use the default key without providing a public key
  # This creates only the private key
  public_key_type = "TYPE_X509_PEM_FILE"
}

# Store service account key in a local file if specified
resource "local_file" "service_account_key" {
  count = var.create_service_account && var.generate_service_account_key && var.output_service_account_key_file != "" ? 1 : 0
  
  filename = var.output_service_account_key_file
  content  = base64decode(google_service_account_key.zenml_sa_key[0].private_key)
  
  # Make file only accessible to owner
  file_permission = "0600"
}

# Authentication configuration for service connectors
locals {
  # Determine which authentication configuration to use based on auth_method
  zenml_auth_config = {
    # For service-account, include the service account JSON
    "service-account" = {
      project_id           = var.project_id
      service_account_json = local.service_account_json
    }
    
    # For implicit authentication, only include project ID
    "implicit" = {
      project_id = var.project_id
    }
    
    # For user-account, only include project ID
    "user-account" = {
      project_id = var.project_id
    }
    
    # For external-account, only include project ID
    "external-account" = {
      project_id = var.project_id
    }
    
    # For oauth2-token, only include project ID
    "oauth2-token" = {
      project_id = var.project_id
    }
    
    # For impersonation, only include project ID
    "impersonation" = {
      project_id = var.project_id
    }
  }
  
  # Use the appropriate auth config based on the selected method
  connector_auth_config = local.zenml_auth_config[var.auth_method]
}

# Create a service connector for GCS
resource "zenml_service_connector" "gcs" {
  name          = "gcp-${var.stack_name}-gcs"
  type          = "gcp"
  auth_method   = var.auth_method
  resource_type = "gcs-bucket"
  resource_id   = local.bucket_name
  configuration = local.connector_auth_config
}

# Create a service connector for GKE
resource "zenml_service_connector" "gke" {
  name          = "gcp-${var.stack_name}-gke"
  type          = "gcp"
  auth_method   = var.auth_method
  resource_type = "kubernetes-cluster"
  resource_id   = var.existing_cluster_name
  configuration = local.connector_auth_config
}

# Create a service connector for GCR
resource "zenml_service_connector" "gcr" {
  name          = "gcp-${var.stack_name}-gcr"
  type          = "gcp"
  auth_method   = var.auth_method
  resource_type = "docker-registry"
  resource_id   = local.container_registry_uri
  configuration = local.connector_auth_config
}

# Register the GCP artifact store component
resource "zenml_stack_component" "artifact_store" {
  name   = "gcp-artifact-store-${var.stack_name}"
  type   = "artifact_store"
  flavor = "gcp"

  configuration = {
    # Use local.bucket_name which handles both existing and new buckets
    path = "gs://${local.bucket_name}"
  }

  connector_id = zenml_service_connector.gcs.id
  
  # Add helpful labels
  labels = {
    managed_by = "terraform"
    source     = var.create_resources ? "terraform-created" : "existing"
  }
}

# Register the GCP container registry component
resource "zenml_stack_component" "container_registry" {
  name   = "gcp-container-registry-${var.stack_name}"
  type   = "container_registry"
  flavor = "gcp"

  configuration = {
    # Use local.container_registry_uri which handles both existing and new registries
    uri = local.container_registry_uri
  }

  connector_id = zenml_service_connector.gcr.id
  
  # Add helpful labels
  labels = {
    managed_by = "terraform"
    source     = var.create_resources ? "terraform-created" : "existing"
  }
}

# Register a KAI Scheduler orchestrator with fractional GPU support
resource "zenml_stack_component" "kai_gpu_sharing_orchestrator" {
  name   = "kai-gpu-sharing-${var.stack_name}"
  type   = "orchestrator"
  flavor = "kubernetes"

  configuration = {
    kubernetes_context   = var.kubernetes_context
    kubernetes_namespace = var.kubernetes_namespace

    # KAI Scheduler configuration with GPU sharing
    pod_settings = jsonencode({
      scheduler_name = "kai-scheduler"
      annotations = {
        # Use configured GPU fraction or default to 0.5
        "gpu-fraction" = var.gpu_fraction
      }
      "labels" = {
        # Use configured queue name or default to "test"
        "runai/queue" = var.kai_scheduler_queue
      },
      tolerations = [
        {
          key      = "nvidia.com/gpu"
          operator = "Equal"
          value    = "present"
          effect   = "NoSchedule"
        }
      ],
      node_selector = {
        # Use configured GPU type or default to "nvidia-tesla-t4"
        "cloud.google.com/gke-accelerator" = var.gpu_type
      },
      container_environment = {
        "NVIDIA_DRIVER_CAPABILITIES" = "compute,utility",
        "NVIDIA_REQUIRE_CUDA"       = "cuda>=11.0"
      }
    })
  }

  connector_id = zenml_service_connector.gke.id
  
  # Add helpful labels
  labels = {
    managed_by = "terraform"
    gpu_type   = var.gpu_type
  }
}

# Create the ZenML stack with all components
resource "zenml_stack" "kai_stack" {
  name = var.stack_name

  components = {
    orchestrator       = zenml_stack_component.kai_gpu_sharing_orchestrator.id
    artifact_store     = zenml_stack_component.artifact_store.id
    container_registry = zenml_stack_component.container_registry.id
  }
  
  # Add helpful labels
  labels = {
    managed_by          = "terraform"
    includes_kai        = "true"
    gcp_project         = var.project_id
    resources_created   = var.create_resources ? "true" : "false"
    service_account_new = var.create_service_account ? "true" : "false"
  }
}
