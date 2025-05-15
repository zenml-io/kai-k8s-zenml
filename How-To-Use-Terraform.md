# How to Use Terraform with KAI and ZenML

This guide explains how to use the enhanced Terraform configuration in this repository to set up a Kubernetes cluster with GPU nodes, KAI Scheduler, and ZenML integration. The Terraform setup now automatically provisions GCS buckets and Google Container Registry resources, making it easier to get started.

## Prerequisites

1. Install the required tools:
   - [Google Cloud SDK](https://cloud.google.com/sdk/docs/install)
   - [Terraform](https://www.terraform.io/downloads.html) (v1.0.0+)
   - [kubectl](https://kubernetes.io/docs/tasks/tools/install-kubectl/)
   - [Helm](https://helm.sh/docs/intro/install/)

2. Ensure you're authenticated with Google Cloud:
   ```bash
   gcloud auth login
   gcloud config set project YOUR_GCP_PROJECT_ID
   ```

3. For development/testing, configure application default credentials:
   ```bash
   gcloud auth application-default login
   ```

## Step 1: Configure Terraform

1. Navigate to the terraform directory:
   ```bash
   cd terraform
   ```

2. Create a copy of the example tfvars file:
   ```bash
   cp terraform.tfvars.example terraform.tfvars
   ```

3. Edit terraform.tfvars with your desired settings:
   ```bash
   nano terraform.tfvars
   # or
   vim terraform.tfvars
   ```

4. At minimum, configure these key settings:
   - `project_id`: Your GCP project ID
   - `region` and `zone`: GCP region and zone for resources
   - `existing_cluster_name`: Name of your GKE cluster
   - `kubernetes_context`: Context for connecting to your GKE cluster

### Key Configuration Options

The Terraform configuration now supports the following key features:

#### Resource Creation (New!)
- `create_resources = true`: Automatically creates GCS bucket and Artifact Registry
- `create_resources = false`: Uses existing GCS bucket and Container Registry

#### Storage Configuration
- Automatic GCS bucket naming with random suffix
- Configurable bucket settings (versioning, storage class, retention)

#### Container Registry
- Uses modern Artifact Registry with unique naming
- Configurable settings for registry location and format

#### Service Account Management (New!)
- `create_service_account = true`: Creates a dedicated service account with proper permissions
- `auth_method`: Choose between "service-account", "implicit", "user-account", or other supported authentication methods
- Multiple options for providing service account credentials

#### KAI Scheduler Configuration
- `gpu_fraction`: Configure GPU sharing fraction (0.0-1.0)
- `kai_scheduler_queue`: Set the KAI Scheduler queue name
- `gpu_type`: Specify the GPU type to target

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

After the deployment completes, you'll see a detailed summary of all created resources including:
- GCS bucket information
- Container registry URI
- Service account details (if created)
- ZenML stack configuration

## Step 5: Configure kubectl

Configure kubectl to connect to your cluster:

```bash
$(terraform output -raw kubectl_command)
```

**Note:** This command assumes you are running it from within the `terraform/` directory. If you've changed directories, ensure you navigate back to the `terraform/` directory before executing this command.

## Step 6: Apply KAI Scheduler Queue Configuration

Apply the predefined queue configuration:

```bash
$(terraform output -raw apply_queue_config_command)
```

## Step 7: Verify the Installation

Check that all components are running correctly:

```bash
# Verify KAI Scheduler pods
kubectl get pods -n kai-scheduler

# Verify Node Feature Discovery
kubectl get pods -n node-feature-discovery

# Verify GPU nodes
kubectl get nodes -l accelerator=nvidia-gpu
```

## Step 8: Using ZenML with KAI Scheduler

The ZenML stack is automatically registered by Terraform. Verify the registered stack:

```bash
zenml stack describe $(terraform output -raw stack_name)
```

Set the stack as active:

```bash
zenml stack set $(terraform output -raw stack_name)
```

### Configure GPU Steps in ZenML Pipelines

When defining ZenML steps that need GPU resources, use the KAI Scheduler annotations:

```python
@step(
    settings={
        "kubernetes": {
            # KAI Scheduler queue (matches configuration in Terraform)
            "labels": {"runai/queue": "test"},
            "scheduler_name": "kai-scheduler",
            # GPU configuration (using fractional GPU)
            "annotations": {
                "gpu-fraction": "0.5"  # Request 50% of GPU resources
            },
            # Target GPU nodes
            "node_selector": {
                "cloud.google.com/gke-accelerator": "nvidia-tesla-t4"
            }
        }
    }
)
def my_gpu_training_step(...):
    # Your GPU training code here
    ...
```

### Run the Test Pipeline

To verify your setup, run the included GPU pipeline:

```bash
python run.py
```

## Advanced Configuration

### Service Account Options

The Terraform configuration supports multiple authentication methods:

1. **Using an existing service account key**:
   ```hcl
   # In terraform.tfvars
   auth_method = "service-account"
   service_account_key_file = "path/to/your/key.json"
   ```

2. **Creating a new service account with automatic key generation**:
   ```hcl
   create_service_account = true
   generate_service_account_key = true
   output_service_account_key_file = "keys/generated-key.json"
   ```

3. **Using implicit authentication**:
   ```hcl
   auth_method = "implicit"
   ```

4. **Using user account**:
   ```hcl
   auth_method = "user-account"
   ```

### GPU Sharing Configuration

The Terraform configuration includes several options for GPU sharing:

1. **Fractional GPU**:
   ```hcl
   gpu_fraction = "0.5"  # Use 50% of a GPU
   ```

2. **Custom Queue**:
   ```hcl
   kai_scheduler_queue = "my-queue"  # Use a custom queue name
   ```

3. **GPU Type Selection**:
   ```hcl
   gpu_type = "nvidia-tesla-t4"  # Target specific GPU type
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

2. **Authentication errors**:
   - Ensure your service account has required permissions:
     - `roles/storage.admin` for GCS buckets (includes storage.buckets.get and objects.*)
     - `roles/artifactregistry.admin` for Artifact Registry access
     - `roles/container.developer` for GKE access
   - Check service account key format and permissions
   - If you see "invalid auth_method" errors, ensure you're using one of: "service-account", "implicit", "user-account", "external-account", "oauth2-token", or "impersonation"

3. **Resource creation errors**:
   - Verify your GCP project has required APIs enabled
   - Check for naming conflicts or quota limitations
   - Ensure region/zone settings match your GKE cluster

4. **ZenML integration issues**:
   - Verify ZenML is properly configured with server and API key
   - Check stack registration: `zenml stack list`
   - Ensure stack components are configured correctly: `zenml stack describe
     $(terraform output -raw stack_name)`
