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
- **NVIDIA GPU Operator** or the GKE driver-installer DaemonSet
  - Helm: `helm install gpu-operator nvidia/gpu-operator -n gpu-operator --create-namespace`
  - GKE COS shortcut: `kubectl apply -f https://raw.githubusercontent.com/GoogleCloudPlatform/container-engine-accelerators/master/nvidia-driver-installer/cos/daemonset-preloaded.yaml`

## Step 1: Set Up NVIDIA KAI Scheduler

KAI Scheduler enables efficient GPU scheduling, including features like GPU sharing, which allows multiple workloads to share the same GPU.

### Install KAI Scheduler with Helm

```bash
# Add the NVIDIA Helm repository
helm repo add nvidia-k8s https://helm.ngc.nvidia.com/nvidia/k8s
helm repo update

# Install KAI Scheduler with GPU sharing and CDI enabled
helm upgrade -i kai-scheduler nvidia-k8s/kai-scheduler \
  --create-namespace \
  --namespace kai-scheduler \
  --set global.registry=nvcr.io/nvidia/k8s \
  --set global.gpuSharing=true \
  --set binder.additionalArgs[0]="--cdi-enabled=true"
```

### Verify KAI Scheduler Installation

```bash
# Check the KAI Scheduler pods
kubectl get pods -n kai-scheduler

# Verify GPU sharing is enabled
kubectl -n kai-scheduler get deployment binder -o json | grep -i gpu-sharing
# Should output: "--gpu-sharing-enabled=true"

# Verify CDI is enabled
kubectl -n kai-scheduler get deployment binder -o json | grep -i cdi
# Should output: "--cdi-enabled=true"
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

# Verify GPU driver is available
kubectl get pods -n nvidia-gpu-operator # If using GPU Operator
# or
kubectl get daemonsets -n kube-system nvidia-driver-installer # If using GKE driver installer
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

1. **GPU Driver Requirements**: There are two approaches to setting up GPU drivers:
   - **GKE COS nodes**: Use Google's driver-installer DaemonSet
   - **Ubuntu/RHEL nodes**: Install the NVIDIA GPU Operator

2. **Node Feature Discovery**: NFD is essential for proper GPU detection and scheduling.

3. **Queue Configuration**: KAI Scheduler requires queues to be defined as Kubernetes custom resources with the `scheduling.run.ai/v1` API type (verify with `kubectl api-resources | grep queue`).

4. **Pod Requirements**: Pods must include both:
   - The correct queue label (`runai/queue: <queue-name>`)
   - The scheduler explicitly set (`schedulerName: kai-scheduler`)

5. **GPU Sharing Requirements**:
   - GPU sharing must be explicitly enabled in KAI Scheduler
   - When using `gpu-fraction` or `gpu-memory` annotations, do NOT specify `nvidia.com/gpu` resource requests/limits
   - Fractional GPUs work only when CDI is enabled (see install step)
   - Pods need both `schedulerName: kai-scheduler` and `runai/queue` label

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
- Check CDI is enabled:
  ```bash
  kubectl -n kai-scheduler get deployment binder -o json | grep -i cdi
  # Should output: "--cdi-enabled=true"
  ```
- Check for errors with:
  ```bash
  kubectl describe pod <pod-name>
  ```
- Common errors include:
  - "cannot have both GPU fraction request and whole GPU resource request/limit" - Remove nvidia.com/gpu resource requests
  - "attempting to create a pod with gpu sharing request, while GPU sharing is disabled" - Enable GPU sharing
  - "unable to initialize NVML" - Install the GPU Operator or driver-installer DaemonSet
  - "no devices found" - Ensure CDI is enabled with `--cdi-enabled=true`
- Examine KAI Scheduler logs:
  ```bash
  kubectl -n kai-scheduler logs deployment/binder
  kubectl -n kai-scheduler logs deployment/scheduler
  ```

### NVML Issues

If you encounter "unable to initialize NVML" errors:
- This typically means the NVIDIA drivers aren't properly installed
- For GKE COS nodes: Reapply the driver installer DaemonSet
- For Ubuntu nodes: Verify the GPU Operator is properly installed

## Clean Up

To tear down the infrastructure:

```bash
cd terraform
terraform destroy
```

This will remove all resources created by Terraform, including the GKE cluster and associated components.

## References

- [ZenML Documentation](https://docs.zenml.io/)
- [NVIDIA KAI Scheduler GitHub](https://github.com/NVIDIA/KAI-Scheduler)
- [NVIDIA KAI Scheduler Documentation](https://docs.nvidia.com/kai-scheduler/index.html)
- [Google Kubernetes Engine Documentation](https://cloud.google.com/kubernetes-engine/docs)
- [Terraform GCP Provider Documentation](https://registry.terraform.io/providers/hashicorp/google/latest/docs)