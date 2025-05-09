output "stack_name" {
  value       = zenml_stack.kai_stack.name
  description = "ZenML Stack Name"
}

output "gcs_bucket_name" {
  value       = google_storage_bucket.artifact_store.name
  description = "GCS bucket name for ZenML artifacts"
}

output "gke_cluster_name" {
  value       = data.google_container_cluster.existing_cluster.name
  description = "GKE cluster name"
}

output "gke_cluster_endpoint" {
  value       = data.google_container_cluster.existing_cluster.endpoint
  description = "GKE cluster endpoint"
  sensitive   = true
}

output "kubectl_command" {
  value       = "gcloud container clusters get-credentials ${data.google_container_cluster.existing_cluster.name} --zone ${var.zone} --project ${var.project_id}"
  description = "Command to configure kubectl"
}

output "apply_queue_config_command" {
  value       = "kubectl apply -f ../queues.yaml --context=$(kubectl config current-context)"
  description = "Command to apply KAI Scheduler queue configuration"
}

output "zenml_run_command" {
  value       = "zenml stack set ${var.stack_name} && python ../gpu_pipeline.py"
  description = "Command to run the GPU pipeline with ZenML"
}

output "kai_queue_usage_example" {
  value       = <<-EOT
    # Example of using KAI Scheduler in a pod spec:
    
    kind: Pod
    apiVersion: v1
    metadata:
      name: example-gpu-job
      labels:
        runai/queue: test  # Use the test queue we created
    spec:
      schedulerName: kai-scheduler
      containers:
      - name: gpu-container
        image: nvidia/cuda:11.6.2-base-ubuntu20.04
        command: ["nvidia-smi"]
        resources:
          limits:
            nvidia.com/gpu: 1
  EOT
  description = "Example of how to use KAI Scheduler in pod specifications"
}