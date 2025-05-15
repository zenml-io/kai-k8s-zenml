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
- PyTorch and scikit-learn integrations installed for ZenML:
  ```bash
  # Install required ZenML integrations
  zenml integration install pytorch sklearn
  # Alternatively, you can install from requirements.txt
  pip install -r requirements.txt
  ```
- **NVIDIA GPU Operator** or the GKE driver-installer DaemonSet
  - Helm: `helm install gpu-operator nvidia/gpu-operator -n gpu-operator --create-namespace`
  - GKE COS shortcut: `kubectl apply -f https://raw.githubusercontent.com/GoogleCloudPlatform/container-engine-accelerators/master/nvidia-driver-installer/cos/daemonset-preloaded.yaml`

## Step 1: Set Up NVIDIA GPU Operator and KAI Scheduler

KAI Scheduler enables efficient GPU scheduling, including features like GPU sharing, which allows multiple workloads to share the same GPU.

### Install NVIDIA GPU Operator

First, create a namespace and resource quota for the GPU operator:

```bash
kubectl apply -f - <<EOF
apiVersion: v1
kind: Namespace
metadata:
  name: gpu-operator
---
apiVersion: v1
kind: ResourceQuota
metadata:
  name: gpu-operator-quota
  namespace: gpu-operator
spec:
  hard:
    pods: 100
  scopeSelector:
    matchExpressions:
    - operator: In
      scopeName: PriorityClass
      values:
        - system-node-critical
        - system-cluster-critical
EOF
```

Apply the NVIDIA driver installer for GKE COS nodes:

```bash
kubectl apply -f https://raw.githubusercontent.com/GoogleCloudPlatform/container-engine-accelerators/master/nvidia-driver-installer/cos/daemonset-preloaded.yaml
```

Install the NVIDIA GPU Operator with Helm:

```bash
helm install --wait --generate-name \
    -n gpu-operator \
    nvidia/gpu-operator \
    --version=v25.3.0 \
    --set hostPaths.driverInstallDir=/home/kubernetes/bin/nvidia \
    --set toolkit.installDir=/home/kubernetes/bin/nvidia \
    --set cdi.enabled=true \
    --set cdi.default=true \
    --set driver.enabled=false
```

Verify the GPU Operator installation:

```bash
kubectl get pods -n gpu-operator
```

All pods should be in a Running state (except for the nvidia-cuda-validator which should be Completed).

### Install KAI Scheduler with GPU Sharing Enabled

```bash
# Add the NVIDIA Helm repository
helm repo add nvidia-k8s https://helm.ngc.nvidia.com/nvidia/k8s
helm repo update

# Install KAI Scheduler with GPU sharing and CDI enabled
helm upgrade -i kai-scheduler nvidia-k8s/kai-scheduler \
  -n kai-scheduler --create-namespace \
  --set "global.registry=nvcr.io/nvidia/k8s" \
  --set "global.gpuSharing=true" \
  --set binder.additionalArgs[0]="--cdi-enabled=true"
```

### Verify KAI Scheduler Installation

```bash
# Check the KAI Scheduler pods
kubectl get pods -n kai-scheduler
```

You should see three pods: binder, podgrouper, and scheduler, all in the Running state.

### Configure Queues for Resource Allocation

KAI Scheduler requires a queue configuration for workload management:

```bash
kubectl apply -f - <<EOF
apiVersion: scheduling.run.ai/v2
kind: Queue
metadata:
  name: default
spec:
  resources:
    cpu:
      quota: -1
      limit: -1
      overQuotaWeight: 1
    gpu:
      quota: -1
      limit: -1
      overQuotaWeight: 1
    memory:
      quota: -1
      limit: -1
      overQuotaWeight: 1
---
apiVersion: scheduling.run.ai/v2
kind: Queue
metadata:
  name: test
spec:
  parentQueue: default
  resources:
    cpu:
      quota: -1
      limit: -1
      overQuotaWeight: 1
    gpu:
      quota: -1
      limit: -1
      overQuotaWeight: 1
    memory:
      quota: -1
      limit: -1
      overQuotaWeight: 1
EOF
```

## Step 2: Deploy Infrastructure with Terraform

For detailed instructions, see [How-To-Use-Terraform.md](How-To-Use-Terraform.md).

### New: Automatic Resource Provisioning

Our enhanced Terraform configuration now automatically provisions GCS buckets and Google Container Registry resources. Key features include:

- **Automatic Resource Creation**: Creates GCS bucket and Artifact Registry with unique names
- **Flexible Authentication**: Supports service account keys, workload identity, and application default credentials
- **Service Account Management**: Optionally creates a dedicated service account with proper permissions
- **Configurable GPU Settings**: Easily customize GPU sharing parameters

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

> **Important Note:** If you're using an existing service account (rather than creating a new one), ensure it has the necessary permissions:
> - `roles/storage.admin` for GCS buckets
> - `roles/artifactregistry.admin` for Artifact Registry
> - `roles/container.developer` for GKE access
> 
> Without these permissions, service connector creation may fail with authorization errors.

After deployment completes, you'll see a detailed summary of all created resources including:
- GCS bucket information
- Container registry URI
- Service account details (if created)
- ZenML stack configuration

### Configure kubectl and Queue System

```bash
# Configure kubectl to connect to your cluster
$(terraform output -raw kubectl_command)

# Apply KAI Scheduler queue configurations
$(terraform output -raw apply_queue_config_command)
```

The Terraform configuration will automatically register your ZenML stack.

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

After deploying the infrastructure, run the included GPU test pipeline to verify everything works correctly.

### Run the Test Pipeline

```bash
# Return to the project root
cd ..

# Build the Docker image used by the pipeline (using Dockerfile.pytorch)
# NOTE: Replace "yourusername" with your own Docker Hub username or container registry prefix
docker build -t yourusername/pytorch-zenml-gpu:root -f Dockerfile.pytorch .
docker push yourusername/pytorch-zenml-gpu:root

# IMPORTANT: After building and pushing the image, update the parent_image in run.py 
# to match your username instead of "strickvl/"

# Run the GPU test pipeline
python run.py
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

KAI Scheduler supports multiple approaches for GPU sharing. Our implementation in run.py uses the following configuration:

### Current Implementation (Fractional GPU with Node Targeting)

```python
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
```

### Alternative: Using Specific GPU Memory (e.g., 5120 MiB)

Instead of using gpu-fraction, you can specify an exact amount of GPU memory:

```python
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
        "labels": {
            "runai/queue": "test"  # Required for KAI Scheduler
        },
        "annotations": {
            "gpu-memory": "5120",  # Request 5120 MiB of GPU memory
            "gpu-type": "nvidia-tesla-t4",  # Explicitly request T4 GPU type
        },
        # Other settings remain the same
        "node_selector": {
            "cloud.google.com/gke-accelerator": "nvidia-tesla-t4",
            "cloud.google.com/gke-nodepool": "gpu-pool",
        },
        "container_environment": {
            "NVIDIA_DRIVER_CAPABILITIES": "all",
            "NVIDIA_REQUIRE_CUDA": "cuda>=12.2",
        },
        "resources": {
            "requests": {"cpu": "500m", "memory": "1Gi"},
            "limits": {"memory": "2Gi"},
        },
        "security_context": {"privileged": True},
    }
)
```

## Infrastructure Overview

The Terraform configuration in this repository has been enhanced to provide a complete infrastructure solution:

> **Note:** This implementation is currently specific to Google Cloud Platform (GCP). If you wish to use AWS, Azure, or another cloud provider, you will need to adapt the Terraform configuration and Docker setup accordingly. The core KAI Scheduler functionality should work on any Kubernetes cluster with NVIDIA GPUs.

1. **GCS Bucket Creation**: Automatically creates a GCS bucket for ZenML artifacts with:
   - Configurable naming with unique suffixes
   - Lifecycle rules for artifact retention
   - Versioning support
   - Access control configuration

2. **Container Registry**: Creates a Google Artifact Registry for storing container images with:
   - Regional deployment matching your GKE cluster
   - Docker format support
   - Unique naming to avoid conflicts

3. **Service Account Management**:
   - Optional creation of a dedicated service account
   - Least-privilege permissions for GCS, Artifact Registry, and GKE
   - Support for different authentication methods
   - Secure key management and distribution

4. **ZenML Integration**:
   - Automatic stack registration with all components
   - Configurable KAI Scheduler settings
   - Support for GPU sharing parameters
   - Descriptive stack and component labels

### Docker Image

This repository includes **Dockerfile.pytorch** which creates the base PyTorch image used in the GPU test pipeline. This image includes:

- CUDA 12.1 and cuDNN 8 for GPU acceleration 
- PyTorch 2.2.0 for deep learning
- scikit-learn for machine learning tasks
- ZenML and its GCP dependencies
- Kubernetes client libraries
- Various Google Cloud SDKs

The Dockerfile is optimized for GCP environments but can be adapted for other cloud providers by modifying the included dependencies.

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

## Acknowledgments

The installation instructions for NVIDIA GPU Operator and KAI Scheduler are adapted from the excellent article by Exostellar:
- [GPU Sharing in Kubernetes: NVIDIA KAI vs Exostellar SDG](https://exostellar.io/2025/04/08/gpu-sharing-in-kubernetes-nvidia-kai-vs-exostellar-sdg/)

## References

- [ZenML Documentation](https://docs.zenml.io/)
- [NVIDIA KAI Scheduler GitHub](https://github.com/NVIDIA/KAI-Scheduler)
- [NVIDIA KAI Scheduler Documentation](https://docs.nvidia.com/kai-scheduler/index.html)
- [Google Kubernetes Engine Documentation](https://cloud.google.com/kubernetes-engine/docs)
 - [Terraform GCP Provider Documentation](https://registry.terraform.io/providers/hashicorp/google/latest/docs)
