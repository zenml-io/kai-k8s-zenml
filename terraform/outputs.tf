output "stack_name" {
  value       = zenml_stack.kai_stack.name
  description = "ZenML Stack Name"
}

output "stack_id" {
  value       = zenml_stack.kai_stack.id
  description = "ZenML Stack ID"
}

output "gcs_bucket_name" {
  value       = var.create_resources ? google_storage_bucket.artifact_store[0].name : data.google_storage_bucket.artifact_store[0].name
  description = "GCS bucket name for ZenML artifacts"
}

output "gcs_bucket_url" {
  value       = "gs://${var.create_resources ? google_storage_bucket.artifact_store[0].name : data.google_storage_bucket.artifact_store[0].name}"
  description = "GCS bucket URL for ZenML artifacts"
}

output "container_registry_uri" {
  value       = local.container_registry_uri
  description = "URI for the container registry"
}

output "resources_created" {
  value       = var.create_resources ? "New GCS bucket and Artifact Registry have been created." : "Using existing GCS bucket and Container Registry resources."
  description = "Indicates whether new resources were created"
}

output "service_account_created" {
  value       = var.create_service_account ? "New service account has been created: ${local.service_account_email}" : "Using existing service account credentials."
  description = "Indicates whether a new service account was created"
}

output "service_account_email" {
  value       = local.service_account_email
  description = "Email of the created service account (if create_service_account is true)"
}

output "gke_cluster_name" {
  value       = var.existing_cluster_name
  description = "GKE cluster name"
}

output "kubectl_command" {
  value       = "gcloud container clusters get-credentials ${var.existing_cluster_name} --zone ${var.zone} --project ${var.project_id}"
  description = "Command to configure kubectl"
}

output "apply_queue_config_command" {
  value       = "kubectl apply -f ../queues.yaml --context=${var.kubernetes_context}"
  description = "Command to apply KAI Scheduler queue configuration"
}

output "verify_stack_command" {
  value       = "zenml stack describe ${zenml_stack.kai_stack.name}"
  description = "Command to verify the stack configuration"
}

output "set_active_stack_command" {
  value       = "zenml stack set ${zenml_stack.kai_stack.name}"
  description = "Command to set this stack as active"
}

output "run_gpu_pipeline" {
  value       = "python ../run.py"
  description = "Command to run the GPU test pipeline"
}

output "kai_queue_usage_example" {
  value       = <<-EOT
    # Example of using KAI Scheduler in a pod spec:
    
    kind: Pod
    apiVersion: v1
    metadata:
      name: example-gpu-job
      labels:
        runai/queue: ${var.kai_scheduler_queue}  # Using the configured queue
      annotations:
        gpu-fraction: "${var.gpu_fraction}"      # Using the configured GPU fraction
    spec:
      schedulerName: kai-scheduler
      containers:
      - name: gpu-container
        image: nvidia/cuda:11.6.2-base-ubuntu20.04
        command: ["nvidia-smi"]
        resources:
          limits:
            nvidia.com/gpu: 1
      nodeSelector:
        cloud.google.com/gke-accelerator: ${var.gpu_type}  # Using the configured GPU type
  EOT
  description = "Example of how to use KAI Scheduler in pod specifications"
}

output "zenml_components" {
  value       = "Created ZenML stack '${var.stack_name}' with the following components:\n  - Artifact Store: ${zenml_stack_component.artifact_store.name}\n  - Container Registry: ${zenml_stack_component.container_registry.name}\n  - Orchestrator: ${zenml_stack_component.kai_gpu_sharing_orchestrator.name} (KAI Scheduler with GPU sharing)"
  description = "Summary of ZenML stack components"
}

output "resource_summary" {
  value       = <<-EOT
    ZenML Stack Configuration Summary:
    
    - Stack name: ${var.stack_name}
    - Project ID: ${var.project_id}
    - Region: ${var.region}
    
    Storage:
    - Bucket name: ${local.bucket_name}
    - Bucket URL: gs://${local.bucket_name}
    - ${var.create_resources ? "✅ Created new bucket" : "🔄 Using existing bucket"}
    
    Container Registry:
    - Registry URI: ${local.container_registry_uri}
    - ${var.create_resources ? "✅ Created new registry" : "🔄 Using existing registry"}
    
    Authentication:
    - Authentication method: ${var.auth_method}
    - ${var.create_service_account ? "✅ Created new service account: ${local.service_account_email}" : "🔄 Using existing service account credentials"}
    
    KAI Scheduler:
    - GPU fraction: ${var.gpu_fraction}
    - Queue: ${var.kai_scheduler_queue}
    - GPU type: ${var.gpu_type}
  EOT
  description = "Summary of all created resources"
}