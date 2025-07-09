"""
Configuration settings for Docker containers and Kubernetes orchestrator.
"""

from kubernetes.client.models import V1Toleration
from zenml.config import DockerSettings
from zenml.integrations.kubernetes.flavors.kubernetes_orchestrator_flavor import (
    KubernetesOrchestratorSettings,
)


# Docker configuration for PyTorch with CUDA support
# IMPORTANT: Replace "strickvl" with your own Docker Hub username or container registry prefix
# that you used when building and pushing the image from Dockerfile.pytorch
docker_settings = DockerSettings(
    parent_image="strickvl/pytorch-zenml-gpu:root",  # Replace "strickvl" with your username
    skip_build=True,
    # Set environment variables for NVIDIA GPU compatibility
    env={
        "NVIDIA_VISIBLE_DEVICES": "all",
        "NVIDIA_DRIVER_CAPABILITIES": "all",  # Use 'all' instead of limited capabilities
        "NVIDIA_REQUIRE_CUDA": "cuda>=12.2",
    },
)

# Kubernetes orchestrator settings for KAI Scheduler with GPU sharing
kubernetes_settings = KubernetesOrchestratorSettings(
    pod_settings={
        # Add tolerations for GPU nodes
        "tolerations": [
            V1Toleration(
                key="nvidia.com/gpu",
                operator="Exists",
                effect="NoSchedule",
            )
        ],
        "scheduler_name": "kai-scheduler",
        # Labels for KAI Scheduler
        "labels": {
            "runai/queue": "test"  # Required for KAI Scheduler
        },
        "annotations": {
            "gpu-fraction": "0.5",  # Use 50% of GPU resources
            "gpu-type": "nvidia-tesla-t4",  # Explicitly request T4 GPU type
        },
        "node_selector": {
            "cloud.google.com/gke-accelerator": "nvidia-tesla-t4",  # Target T4 GPU nodes
            "cloud.google.com/gke-nodepool": "gpu-pool",  # Target specific GPU node pool
        },
        # Add environment variables for NVIDIA GPU compatibility
        "container_environment": {
            "NVIDIA_DRIVER_CAPABILITIES": "all",
            "NVIDIA_REQUIRE_CUDA": "cuda>=12.2",
        },
        # Add CPU and memory resources but no GPU (KAI will handle that via annotation)
        "resources": {
            "requests": {"cpu": "500m", "memory": "1Gi"},
            "limits": {"memory": "2Gi"},
        },
        # Add security context to allow wider device access
        "security_context": {"privileged": True},
    }
) 