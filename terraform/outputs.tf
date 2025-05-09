output "stack_name" {
  value       = zenml_stack.kai_stack.name
  description = "ZenML Stack Name"
}

output "stack_id" {
  value       = zenml_stack.kai_stack.id
  description = "ZenML Stack ID"
}

output "gcs_bucket_name" {
  value       = data.google_storage_bucket.artifact_store.name
  description = "GCS bucket name for ZenML artifacts"
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
  value       = "python ../gpu_pipeline.py"
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