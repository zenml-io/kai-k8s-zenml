output "gke_cluster_name" {
  value       = google_container_cluster.primary.name
  description = "GKE cluster name"
}

output "gcs_bucket_name" {
  value       = google_storage_bucket.artifact_store.name
  description = "GCS bucket name for ZenML artifacts"
}

output "gke_cluster_endpoint" {
  value       = google_container_cluster.primary.endpoint
  description = "GKE cluster endpoint"
  sensitive   = true
}

output "kubectl_command" {
  value       = "gcloud container clusters get-credentials ${google_container_cluster.primary.name} --zone ${var.zone} --project ${var.project_id}"
  description = "Command to configure kubectl"
}

output "kai_scheduler_namespace" {
  value       = kubernetes_namespace.kai_scheduler.metadata[0].name
  description = "Namespace where KAI Scheduler is installed"
}

output "check_kai_pods_command" {
  value       = "kubectl get pods -n ${kubernetes_namespace.kai_scheduler.metadata[0].name}"
  description = "Command to check KAI Scheduler pods"
}

output "zenml_namespace" {
  value       = kubernetes_namespace.zenml.metadata[0].name
  description = "Namespace for running ZenML pipelines"
}

output "apply_queue_config_command" {
  value       = "kubectl apply -f ../queues.yaml --context=$(kubectl config current-context)"
  description = "Command to apply KAI Scheduler queue configuration"
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