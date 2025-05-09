# How to Use Terraform with KAI and ZenML

This guide explains how to use the Terraform configuration in this repository to set up a Kubernetes cluster with GPU nodes, KAI Scheduler, and ZenML integration.

## Prerequisites

1. Install the required tools:
   - [Google Cloud SDK](https://cloud.google.com/sdk/docs/install)
   - [Terraform](https://www.terraform.io/downloads.html) (v1.0.0+)
   - [kubectl](https://kubernetes.io/docs/tasks/tools/install-kubectl/)
   - [Helm](https://helm.sh/docs/intro/install/)

2. Ensure you're authenticated with Google Cloud:
   ```bash
   gcloud auth login
   gcloud config set project zenml-core
   ```

## Step 1: Configure Terraform

1. Navigate to the terraform directory:
   ```bash
   cd terraform
   ```

2. Review and modify `terraform.tfvars` with your desired settings:
   - `project_id`: Your GCP project ID
   - `region` and `zone`: GCP region and zone for resources
   - `node_pool_machine_type`: Machine type for regular nodes
   - `gpu_node_machine_type`: Machine type for GPU nodes
   - `gpu_type`: Type of GPU (e.g., nvidia-tesla-t4)
   - `artifact_store_bucket_name`: Name for GCS bucket used by ZenML

## Step 2: Initialize Terraform

Initialize Terraform to download required providers:

```bash
terraform init
```

## Step 3: Plan the Deployment

Generate a plan to review what resources will be created:

```bash
terraform plan
```

Review the output to ensure everything looks correct.

## Step 4: Apply the Configuration

Deploy the infrastructure:

```bash
terraform apply
```

When prompted, type `yes` to confirm.

## Step 5: Configure kubectl

After the deployment completes, configure kubectl to connect to your cluster:

```bash
$(terraform output -raw kubectl_command)
```

## Step 6: Apply KAI Scheduler Queue Configuration

Apply the predefined queue configuration:

```bash
$(terraform output -raw apply_queue_config_command)
```

## Step 7: Verify the Installation

Check that all components are running correctly:

```bash
# Verify KAI Scheduler pods
$(terraform output -raw check_kai_pods_command)

# Verify Node Feature Discovery
kubectl get pods -n node-feature-discovery

# Verify GPU nodes
kubectl get nodes -l accelerator=nvidia-gpu
```

## Step 8: Using ZenML with KAI Scheduler

1. Register the created cluster with ZenML:

```bash
zenml stack register --name kai-gcp-stack \
  --orchestrator kubernetes \
  --artifact_store gcp \
  --container_registry gcp
```

2. Configure ZenML components:

```bash
zenml orchestrator register kai-k8s \
  --provider=kubernetes \
  --kubernetes_namespace=zenml \
  --kubernetes_context=<get context from kubectl config current-context>

zenml artifact_store register kai-gcs \
  --provider=gcp \
  --path=gs://$(terraform output -raw gcs_bucket_name)
```

3. Configure GPU steps in ZenML pipelines:

When defining ZenML steps that need GPU resources, use the KAI Scheduler annotations:

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

## Clean Up

To destroy all created resources:

```bash
terraform destroy
```

When prompted, type `yes` to confirm.

## Troubleshooting

If you encounter issues:

1. **Pods stuck in "Pending" state**:
   - Check queue configuration: `kubectl get queue -A`
   - Verify pods have correct labels: `kubectl get pods -o yaml`
   - Check GPU node status: `kubectl describe node <gpu-node-name>`

2. **Helm chart installation errors**:
   - Check Helm repository: `helm repo list`
   - Update repositories: `helm repo update`

3. **Terraform errors**:
   - Ensure GCP authentication is current: `gcloud auth application-default login`
   - Check quota limitations in your GCP project