# NVIDIA KAI Scheduler with ZenML on GCP

This repository demonstrates how to set up NVIDIA KAI Scheduler (Kubernetes AI Scheduler) with ZenML on a GKE cluster. KAI Scheduler enables efficient GPU scheduling in Kubernetes, making it an ideal choice for ML workloads.

## Introduction

NVIDIA KAI Scheduler is specifically designed to optimize GPU resource allocation in Kubernetes clusters. This guide will walk you through three key steps:

1. **Install KAI Scheduler**: Set up the scheduler on your Kubernetes cluster
2. **Configure with Terraform**: Register your infrastructure with ZenML using Terraform
3. **Verify with GPU Pipeline**: Run a test ML pipeline to validate your setup

## Prerequisites

- Google Cloud Platform account with sufficient permissions
- [Google Cloud SDK](https://cloud.google.com/sdk/docs/install) installed and configured
- [Terraform](https://www.terraform.io/downloads.html) (v1.0.0+) installed
- [kubectl](https://kubernetes.io/docs/tasks/tools/install-kubectl/) installed
- [Helm](https://helm.sh/docs/intro/install/) installed
- [ZenML](https://docs.zenml.io/getting-started/installation) (v0.52.0+) installed

## Step 1: Set Up NVIDIA KAI Scheduler

KAI Scheduler enables efficient GPU scheduling, including features like GPU sharing, which allows multiple workloads to share the same GPU.

### Install KAI Scheduler with Helm

```bash
# Add the NVIDIA Helm repository
helm repo add nvidia https://helm.ngc.nvidia.com/nvidia
helm repo update

# Install KAI Scheduler with GPU sharing enabled
helm install kai-scheduler nvidia/kai-scheduler \
  --create-namespace \
  --namespace kai-scheduler \
  --set global.gpuSharing=true
```

> **Note**: If you've already installed KAI Scheduler without GPU sharing, you can enable it by patching the binder deployment:
> ```bash
> kubectl -n kai-scheduler patch deployment binder --type='json' \
>   -p='[{"op": "replace", "path": "/spec/template/spec/containers/0/args/4", "value": "--gpu-sharing-enabled=true"}]'
> ```

### Verify KAI Scheduler Installation

```bash
# Check the KAI Scheduler pods
kubectl get pods -n kai-scheduler

# Verify GPU sharing is enabled
kubectl -n kai-scheduler get deployment binder -o json | grep -i gpu-sharing
# Should output: "--gpu-sharing-enabled=true"
```

### Configure Queues for Resource Allocation

KAI Scheduler uses a hierarchical queue system:

```bash
# Apply queue configuration
kubectl apply -f queues.yaml
```

## Step 2: Deploy Infrastructure with Terraform

For detailed instructions, see [How-To-Use-Terraform.md](How-To-Use-Terraform.md).

### Set up GCP Authentication and Configure Terraform

```bash
cd terraform
# Create a copy of the example vars file
cp terraform.tfvars.example terraform.tfvars

# Edit terraform.tfvars with your specific settings
nano terraform.tfvars

# For development/testing, we're using oauth2 authentication
# Make sure you're authenticated with gcloud:
gcloud auth application-default login

# Initialize and deploy with Terraform
terraform init
terraform plan  # Review the planned changes
terraform apply # Deploy the infrastructure
```

### Configure kubectl and Queue System

```bash
# Configure kubectl to connect to your cluster
$(terraform output -raw kubectl_command)

# Apply KAI Scheduler queue configurations
$(terraform output -raw apply_queue_config_command)
```

### Verify the Installation

```bash
# Verify KAI Scheduler pods
$(terraform output -raw check_kai_pods_command)

# Verify Node Feature Discovery
kubectl get pods -n node-feature-discovery

# Verify GPU nodes
kubectl get nodes -l accelerator=nvidia-gpu
```

## Step 3: Run the GPU Test Pipeline

After deploying the infrastructure, run the included GPU test pipeline to verify everything works correctly:

### Register ZenML Stack Components

```bash
# Navigate to terraform directory to get outputs
cd terraform

# Register the stack with the deployed infrastructure
zenml stack register --name kai-gcp-stack \
  --orchestrator kubernetes \
  --artifact_store gcp \
  --container_registry gcp

# Set it as the active stack
zenml stack set kai-gcp-stack
```

### Run the Test Pipeline

```bash
# Return to the project root
cd ..

# Build the Docker image used by the pipeline (using Dockerfile.pytorch)
docker build -t strickvl/pytorch-zenml-gpu:root -f Dockerfile.pytorch .

# Run the GPU test pipeline
python gpu_pipeline.py
```

### Expected Output

When successful, you should see output confirming GPU availability:

```
Running pipeline: gpu_pipeline
Step gpu_step starting...
GPU is available: True
Step gpu_step completed successfully!
Pipeline run completed successfully!
```

## GPU Sharing Configuration Options

KAI Scheduler supports multiple approaches for GPU sharing:

### 1. Using Fractional GPU (50% of a GPU)

```python
kubernetes_settings = KubernetesOrchestratorSettings(
    pod_settings={
        # When using KAI Scheduler with gpu-fraction, we don't specify
        # nvidia.com/gpu in the resources section
        "tolerations": [
            V1Toleration(
                key="nvidia.com/gpu",
                operator="Equal",
                value="present",
                effect="NoSchedule",
            )
        ],
        "scheduler_name": "kai-scheduler",
        "labels": {
            "runai/queue": "test"  # Required for KAI Scheduler
        },
        "annotations": {
            "gpu-fraction": "0.5"  # Use 50% of GPU resources
        },
    }
)
```

### 2. Using Specific GPU Memory (e.g., 2000 MiB)

```python
kubernetes_settings = KubernetesOrchestratorSettings(
    pod_settings={
        # When using KAI Scheduler with gpu-memory, we don't specify
        # nvidia.com/gpu in the resources section
        "tolerations": [
            V1Toleration(
                key="nvidia.com/gpu",
                operator="Equal",
                value="present",
                effect="NoSchedule",
            )
        ],
        "scheduler_name": "kai-scheduler",
        "labels": {
            "runai/queue": "test"  # Required for KAI Scheduler
        },
        "annotations": {
            "gpu-memory": "2000"  # Request 2000 MiB of GPU memory
        },
    }
)
```

## Test Jobs and Examples

This repository includes several example job specifications:

1. **GPU Test Job** (`gpu-test-job.yaml`): A simple job that runs `nvidia-smi` to verify GPU access
2. **Fractional GPU Test Job** (`gpu-test-job-fractional.yaml`): Tests 50% GPU sharing
3. **GPU Memory Test Job** (`gpu-test-job-memory.yaml`): Tests specific GPU memory allocation
4. **ML Training Job** (`ml-training-job.yaml`): A PyTorch training job that uses GPU resources
5. **Model Serving Deployment** (`model-serving-deployment.yaml`): A deployment for serving ML models

To run a test job:

```bash
kubectl apply -f gpu-test-job.yaml
```

## Infrastructure Overview

The Terraform configuration in this repository creates:

- A GKE cluster with regular CPU nodes for system workloads
- A dedicated GPU node pool with NVIDIA T4 GPUs
- Node Feature Discovery (NFD) for hardware feature detection
- KAI Scheduler deployment
- A GCS bucket for artifact storage

### Docker Images

This repository includes the following Dockerfiles:

- **Dockerfile.pytorch**: Creates the base PyTorch image `strickvl/pytorch-zenml-gpu:root` used in the GPU test pipeline. This image includes CUDA, PyTorch, and ZenML dependencies required for GPU workloads.
- **Dockerfile.gpu**: Another GPU-enabled image option for specialized use cases.

## Key Learnings and Best Practices

During our setup process, we learned several important lessons:

1. **GKE GPU Driver Management**: On GKE, GPU drivers are pre-installed and managed by the platform. Unlike other Kubernetes distributions, there's no need to install the NVIDIA GPU Operator.

2. **Node Feature Discovery**: NFD is essential for proper GPU detection and scheduling.

3. **Queue Configuration**: KAI Scheduler requires queues to be defined as Kubernetes custom resources with the `scheduling.run.ai/v2` API type.

4. **Pod Requirements**: Pods must include both:
   - The correct queue label (`runai/queue: <queue-name>`)
   - The scheduler explicitly set (`schedulerName: kai-scheduler`)

5. **GPU Sharing Requirements**:
   - GPU sharing must be explicitly enabled in KAI Scheduler
   - When using `gpu-fraction` or `gpu-memory` annotations, do NOT specify `nvidia.com/gpu` resource requests/limits
   - GPU sharing requires KAI Scheduler pods to run with the `--gpu-sharing-enabled=true` argument

## Troubleshooting

### General Issues

If pods remain in "Pending" state:
- Verify queue configuration is correctly applied (`kubectl get queue -A`)
- Check that pods have the proper queue label (`kubectl get pods -o yaml`)
- Ensure the pod specifies the correct scheduler name
- Check GPU resource availability with `kubectl describe node <gpu-node-name>`

### GPU Sharing Issues

If GPU sharing pods are rejected:
- Verify KAI Scheduler has GPU sharing enabled:
  ```bash
  kubectl -n kai-scheduler get deployment binder -o json | grep -i gpu-sharing
  # Should output: "--gpu-sharing-enabled=true"
  ```
- If GPU sharing is disabled, enable it:
  ```bash
  kubectl -n kai-scheduler patch deployment binder --type='json' \
    -p='[{"op": "replace", "path": "/spec/template/spec/containers/0/args/4", "value": "--gpu-sharing-enabled=true"}]'
  ```
- Check for errors with:
  ```bash
  kubectl describe pod <pod-name>
  ```
- Common errors include:
  - "cannot have both GPU fraction request and whole GPU resource request/limit" - Remove nvidia.com/gpu resource requests
  - "attempting to create a pod with gpu sharing request, while GPU sharing is disabled" - Enable GPU sharing
- Examine KAI Scheduler logs:
  ```bash
  kubectl -n kai-scheduler logs deployment/binder
  kubectl -n kai-scheduler logs deployment/scheduler
  ```

## Clean Up

To tear down the infrastructure:

```bash
cd terraform
terraform destroy
```

This will remove all resources created by Terraform, including the GKE cluster and associated components.

## References

- [ZenML Documentation](https://docs.zenml.io/)
- [NVIDIA KAI Scheduler GitHub](https://github.com/NVIDIA/kai-scheduler)
- [NVIDIA KAI Scheduler Documentation](https://docs.nvidia.com/kai-scheduler/index.html)
- [Google Kubernetes Engine Documentation](https://cloud.google.com/kubernetes-engine/docs)
- [Terraform GCP Provider Documentation](https://registry.terraform.io/providers/hashicorp/google/latest/docs)