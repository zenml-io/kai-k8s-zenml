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
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
  zone    = var.zone
}

# Create GKE Cluster
resource "google_container_cluster" "primary" {
  name     = "zenml-kai-cluster-tf"
  location = var.zone

  # We can't create a cluster with no node pool defined, but we want to only use
  # separately managed node pools. So we create the smallest possible default
  # node pool and immediately delete it.
  remove_default_node_pool = true
  initial_node_count       = 1

  # Set up workload identity
  workload_identity_config {
    workload_pool = "${var.project_id}.svc.id.goog"
  }
}

# Create main node pool for standard workloads
resource "google_container_node_pool" "primary_nodes" {
  name       = "default-pool"
  location   = var.zone
  cluster    = google_container_cluster.primary.name
  node_count = var.node_pool_min_count

  autoscaling {
    min_node_count = var.node_pool_min_count
    max_node_count = var.node_pool_max_count
  }

  node_config {
    machine_type = var.node_pool_machine_type
    disk_size_gb = 100

    # Set metadata on the nodes for GKE usage
    oauth_scopes = [
      "https://www.googleapis.com/auth/cloud-platform"
    ]

    # Set up workload identity
    workload_metadata_config {
      mode = "GKE_METADATA"
    }
  }
}

# Create GPU node pool
resource "google_container_node_pool" "gpu_nodes" {
  name       = "gpu-pool"
  location   = var.zone
  cluster    = google_container_cluster.primary.name
  node_count = var.gpu_node_count

  node_config {
    machine_type = var.gpu_node_machine_type
    disk_size_gb = 100
    
    guest_accelerator {
      type  = var.gpu_type
      count = var.gpu_count_per_node
    }
    
    oauth_scopes = [
      "https://www.googleapis.com/auth/cloud-platform"
    ]
    
    workload_metadata_config {
      mode = "GKE_METADATA"
    }
    
    labels = {
      "accelerator" = "nvidia-gpu"
    }

    taint {
      key    = "nvidia.com/gpu"
      value  = "present"
      effect = "NO_SCHEDULE"
    }
  }
  
  depends_on = [google_container_node_pool.primary_nodes]
}

# Configure kubectl provider for post-setup tasks
data "google_client_config" "provider" {}

provider "kubernetes" {
  host  = "https://${google_container_cluster.primary.endpoint}"
  token = data.google_client_config.provider.access_token
  cluster_ca_certificate = base64decode(
    google_container_cluster.primary.master_auth[0].cluster_ca_certificate,
  )
}

provider "helm" {
  kubernetes {
    host  = "https://${google_container_cluster.primary.endpoint}"
    token = data.google_client_config.provider.access_token
    cluster_ca_certificate = base64decode(
      google_container_cluster.primary.master_auth[0].cluster_ca_certificate,
    )
  }
}

# Create GCS bucket for artifact storage
resource "google_storage_bucket" "artifact_store" {
  name          = "${var.artifact_store_bucket_name}-tf"
  location      = var.region
  force_destroy = true

  versioning {
    enabled = var.bucket_versioning_enabled
  }
}

# Install Node Feature Discovery (NFD)
resource "kubernetes_namespace" "nfd" {
  metadata {
    name = "node-feature-discovery"
  }
  
  depends_on = [google_container_node_pool.gpu_nodes]
}

resource "helm_release" "nfd" {
  name       = "nfd"
  repository = "https://kubernetes-sigs.github.io/node-feature-discovery/charts"
  chart      = "node-feature-discovery"
  namespace  = kubernetes_namespace.nfd.metadata[0].name

  depends_on = [kubernetes_namespace.nfd]
}

# Install KAI Scheduler
resource "kubernetes_namespace" "kai_scheduler" {
  metadata {
    name = "kai-scheduler"
  }
  
  depends_on = [helm_release.nfd]
}

resource "helm_release" "kai_scheduler" {
  name       = "kai-scheduler"
  repository = "oci://ghcr.io/nvidia/kai-scheduler"
  chart      = "kai-scheduler"
  namespace  = kubernetes_namespace.kai_scheduler.metadata[0].name
  version    = var.kai_scheduler_version

  depends_on = [kubernetes_namespace.kai_scheduler]
}

# We'll create the queue configurations using kubectl rather than Kubernetes manifest resources
# This avoids issues with the provider configuration and custom resource definitions
# After applying the Terraform configuration, you can apply the queue configuration manually:
# kubectl apply -f queues.yaml

# Create ZenML namespace for running pipelines
resource "kubernetes_namespace" "zenml" {
  metadata {
    name = "zenml"
  }
  
  depends_on = [google_container_cluster.primary]
}