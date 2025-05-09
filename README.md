# NVIDIA KAI Scheduler with ZenML on GCP

This repository demonstrates how to set up NVIDIA KAI Scheduler (Kubernetes AI Scheduler) with ZenML on a GKE cluster. KAI Scheduler enables efficient GPU scheduling in Kubernetes, making it an ideal choice for ML workloads.

## Introduction

NVIDIA KAI Scheduler is specifically designed to optimize GPU resource allocation in Kubernetes clusters. This repository shows how to:

1. Deploy a complete GCP infrastructure using Terraform
2. Configure ZenML to work with GKE and KAI Scheduler
3. Run ML training jobs efficiently on GPU resources

## Infrastructure Overview

The Terraform configuration in this repository creates:

- A GKE cluster with regular CPU nodes for system workloads
- A dedicated GPU node pool with NVIDIA T4 GPUs
- Node Feature Discovery (NFD) for hardware feature detection
- KAI Scheduler deployment
- A GCS bucket for artifact storage

## Prerequisites

- Google Cloud Platform account with sufficient permissions
- [Google Cloud SDK](https://cloud.google.com/sdk/docs/install) installed and configured
- [Terraform](https://www.terraform.io/downloads.html) (v1.0.0+) installed
- [kubectl](https://kubernetes.io/docs/tasks/tools/install-kubectl/) installed
- [Helm](https://helm.sh/docs/intro/install/) installed
- [ZenML](https://docs.zenml.io/getting-started/installation) (v0.52.0+) installed

## Quick Start

For detailed instructions, see [How-To-Use-Terraform.md](How-To-Use-Terraform.md).

### 1. Clone this repository

```bash
git clone https://github.com/your-org/kai-k8s-zenml.git
cd kai-k8s-zenml
```

### 2. Set up GCP Authentication and Configure Terraform

```bash
cd terraform
# Create a copy of the example vars file
cp terraform.tfvars.example terraform.tfvars

# Edit terraform.tfvars with your specific settings
nano terraform.tfvars

# For development/testing, we're using oauth2 authentication
# Make sure you're authenticated with gcloud:
gcloud auth application-default login
# This will use your user credentials for authentication

# Initialize and deploy with Terraform
terraform init
terraform plan  # Review the planned changes
terraform apply # Deploy the infrastructure
```

### 3. Configure kubectl and Queue System

```bash
# Configure kubectl to connect to your cluster
$(terraform output -raw kubectl_command)

# Apply KAI Scheduler queue configurations
$(terraform output -raw apply_queue_config_command)
```

### 4. Verify the installation

```bash
# Verify KAI Scheduler pods
$(terraform output -raw check_kai_pods_command)

# Verify Node Feature Discovery
kubectl get pods -n node-feature-discovery

# Verify GPU nodes
kubectl get nodes -l accelerator=nvidia-gpu
```

## Running ML Workloads with KAI Scheduler

### Queue Configuration

KAI Scheduler uses a hierarchical queue system for resource allocation. The default configuration in `queues.yaml` includes:

- A root "default" queue with unrestricted resource access
- A child "test" queue for running test workloads

### Example Jobs

This repository includes several example job specifications:

1. **GPU Test Job** (`gpu-test-job.yaml`): A simple job that runs `nvidia-smi` to verify GPU access.
2. **ML Training Job** (`ml-training-job.yaml`): A PyTorch training job that uses GPU resources.
3. **Model Serving Deployment** (`model-serving-deployment.yaml`): A deployment for serving ML models.

To run a test job:

```bash
kubectl apply -f gpu-test-job.yaml
```

### Using with ZenML

After deploying the infrastructure with Terraform, you can run ML pipelines with ZenML using KAI Scheduler:

1. Register a ZenML stack with the infrastructure components:
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

2. Run the included GPU test pipeline:
   ```bash
   python gpu_pipeline.py
   ```

3. When defining your own ZenML steps for GPU workloads, use the following configuration with KAI Scheduler:

```python
@step(
    settings={
        "resources": {
            "gpu": 1
        },
        "kubernetes": {
            "labels": {"runai/queue": "test"},
            "scheduler_name": "kai-scheduler"
        }
    }
)
def my_gpu_training_step(...):
    # Your GPU training code here
    ...
```

## Key Learnings and Best Practices

During our setup process, we learned several important lessons:

1. **GKE GPU Driver Management**: On GKE, GPU drivers are pre-installed and managed by the platform. Unlike other Kubernetes distributions, there's no need to install the NVIDIA GPU Operator.

2. **Node Feature Discovery**: NFD is essential for proper GPU detection and scheduling.

3. **Queue Configuration**: KAI Scheduler requires queues to be defined as Kubernetes custom resources with the `scheduling.run.ai/v2` API type.

4. **Pod Requirements**: Pods must include both:
   - The correct queue label (`runai/queue: <queue-name>`)
   - The scheduler explicitly set (`schedulerName: kai-scheduler`)

5. **Resource Requests**: Always specify GPU resource requests in your pod specifications.

## Terraform Configuration for ZenML Stack

The Terraform configuration in the `/terraform` directory sets up a ZenML stack configured to work with the existing KAI-enabled GKE cluster:

- **main.tf**: Registers ZenML stack components using the ZenML provider with GKE and KAI Scheduler
- **variables.tf**: Configurable parameters including cluster name, GCS bucket settings, and service account details
- **outputs.tf**: Provides useful commands and information after deployment
- **terraform.tfvars**: Default configuration values that can be customized

### Authentication Setup

For authentication with GCP, the configuration supports two methods:

1. **Service Account Authentication (Recommended for Production)**
   ```bash
   # Create a service account with appropriate permissions
   gcloud iam service-accounts create zenml-kai-scheduler --display-name="ZenML KAI Scheduler Service Account"

   # Assign necessary roles
   gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
     --member="serviceAccount:zenml-kai-scheduler@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
     --role="roles/storage.admin" --condition=None

   gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
     --member="serviceAccount:zenml-kai-scheduler@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
     --role="roles/container.admin" --condition=None

   # Create and download the key
   mkdir -p keys
   gcloud iam service-accounts keys create keys/zenml-kai-scheduler.json \
     --iam-account=zenml-kai-scheduler@YOUR_PROJECT_ID.iam.gserviceaccount.com

   # Export the key for Terraform to use
   export TF_VAR_gcp_service_account_json="$(cat keys/zenml-kai-scheduler.json)"
   ```

2. **OAuth2 Authentication (For Development/Testing)**
   ```bash
   # Authenticate with your Google account
   gcloud auth application-default login
   ```

### Deployment Steps

To deploy the stack:

```bash
cd terraform

# Copy and customize variables
cp terraform.tfvars.example terraform.tfvars
nano terraform.tfvars  # Edit with your specific settings

# Initialize Terraform
terraform init

# Plan and apply
terraform plan
terraform apply
```

This will register a ZenML stack that's properly configured to use KAI Scheduler for GPU workloads, leveraging your existing GKE cluster. The stack will include:

1. A GCP service connector (using your chosen authentication method)
2. An artifact store component using your GCS bucket
3. A container registry component for GCR
4. A Kubernetes orchestrator configured to use KAI Scheduler
5. A complete ZenML stack combining all these components

After deployment, follow the commands in the Terraform outputs to validate the setup and run GPU pipelines.

## Troubleshooting

If pods remain in "Pending" state:
- Verify queue configuration is correctly applied (`kubectl get queue -A`)
- Check that pods have the proper queue label (`kubectl get pods -o yaml`)
- Ensure the pod specifies the correct scheduler name
- Check GPU resource availability with `kubectl describe node <gpu-node-name>`

## Clean Up

To tear down the infrastructure:

```bash
terraform destroy
```

This will remove all resources created by Terraform, including the GKE cluster and associated components.

## References

- [ZenML Documentation](https://docs.zenml.io/)
- [NVIDIA KAI Scheduler GitHub](https://github.com/NVIDIA/kai-scheduler)
- [NVIDIA KAI Scheduler Documentation](https://docs.nvidia.com/kai-scheduler/index.html)
- [Google Kubernetes Engine Documentation](https://cloud.google.com/kubernetes-engine/docs)
- [Terraform GCP Provider Documentation](https://registry.terraform.io/providers/hashicorp/google/latest/docs)