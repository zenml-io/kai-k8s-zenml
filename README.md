# NVIDIA KAI Scheduler Setup Guide

This guide documents the process of setting up NVIDIA KAI Scheduler (Kubernetes AI Scheduler) on a GKE cluster with GPU nodes.

## Prerequisites

- A GKE cluster with GPU nodes (e.g., NVIDIA T4)
- `kubectl` configured to access your cluster
- `helm` installed

## 1. Verify GPU Node Status

First, check if your GKE cluster has GPU nodes properly configured:

```bash
# List all nodes
kubectl get nodes -o wide

# Check GPU resources on a specific node
kubectl describe node <gpu-node-name> | grep -A5 Capacity
```

## 2. Install NFD (Node Feature Discovery)

NFD helps Kubernetes discover hardware features of nodes:

```bash
# Add NFD Helm repository
helm repo add nfd https://kubernetes-sigs.github.io/node-feature-discovery/charts
helm repo update

# Install NFD
helm install nfd nfd/node-feature-discovery --namespace node-feature-discovery --create-namespace
```

## 3. Install KAI Scheduler

```bash
# Add NVIDIA Helm repository (if not already added)
helm repo add nvidia https://helm.ngc.nvidia.com/nvidia
helm repo update

# Install KAI Scheduler
helm upgrade -i kai-scheduler \
    oci://ghcr.io/nvidia/kai-scheduler/kai-scheduler \
    -n kai-scheduler --create-namespace --version 0.3.0

# Verify KAI Scheduler is running
kubectl get pods -n kai-scheduler
```

## 4. Configure KAI Scheduler Queues

Create the queue configuration YAML file (`queues.yaml`) and apply it:

```bash
kubectl apply -f queues.yaml
```

**Important**: KAI Scheduler uses custom resource definitions for queues. Do not use ConfigMaps for queue configuration.

## 5. Test GPU Workload with KAI Scheduler

Create a test namespace for your GPU workloads:

```bash
kubectl create namespace kai-test
```

Deploy a test GPU pod using the KAI Scheduler:

```bash
kubectl apply -f gpu-test-job.yaml
```

Verify the pod is running and has access to the GPU:

```bash
kubectl get pods -n kai-test
kubectl logs -n kai-test <pod-name>
```

## Configuration Files

### `queues.yaml`

This file defines the queue hierarchy for KAI Scheduler.

### `gpu-test-job.yaml`

This file defines a simple GPU job that uses the KAI Scheduler to run nvidia-smi.

### `ml-training-job.yaml`

This file provides an example of a PyTorch-based ML training job that uses GPU resources via KAI Scheduler.

### `model-serving-deployment.yaml`

This file demonstrates how to deploy a model serving application as a Kubernetes Deployment with KAI Scheduler.

## Troubleshooting

If pods remain in "Pending" state:
- Check if queue configuration is correctly applied
- Verify that pods have the proper queue label (`runai/queue: <queue-name>`)
- Ensure the pod specifies `schedulerName: kai-scheduler`
- Check GPU resource availability with `kubectl describe node <gpu-node-name>`

## Key Learnings

During our setup process, we encountered and resolved several important issues:

1. **Queue Configuration Format**: KAI Scheduler requires queues to be defined as Kubernetes custom resources with the `scheduling.run.ai/v2` API type, not through a ConfigMap.

2. **Queue Hierarchy**: A hierarchical queue system is needed, with a top-level "default" queue and child queues.

3. **Pod Requirements**: Pods must have both:
   - The correct queue label (`runai/queue: <queue-name>`)
   - The scheduler explicitly set (`schedulerName: kai-scheduler`)

4. **GPU Driver Management**: On GKE, GPU drivers are pre-installed and managed by the platform itself. Unlike other Kubernetes distributions, there's no need to install the NVIDIA GPU Operator.

5. **NFD Requirements**: Node Feature Discovery helps the system identify hardware features including GPUs, making it a crucial component for proper GPU scheduling.

## Note for GKE Users

On GKE, GPU drivers are pre-installed and managed by GKE itself. Unlike other Kubernetes distributions, you do not need to install the NVIDIA GPU Operator on GKE.