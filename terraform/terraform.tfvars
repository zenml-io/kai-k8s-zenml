# GCP Project Configuration
project_id = "zenml-core"
region     = "us-central1"
zone       = "us-central1-a"

# Existing Cluster Configuration
existing_cluster_name = "zenml-kai-cluster"

# ZenML Stack Configuration
stack_name = "kai-gcp-stack"

# Storage Configuration
artifact_store_bucket_name = "zenml-core-zenml-artifacts"
bucket_versioning_enabled  = true

# Container Registry
container_registry_uri = "gcr.io/zenml-core/zenml"

# Namespace Configuration
create_zenml_namespace = false