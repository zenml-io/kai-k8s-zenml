#!/bin/bash
set -e

echo "Starting scale-up of GKE cluster node pools"

# Scale up default-pool back to 2 nodes
echo "Scaling up default-pool to 2 nodes..."
gcloud container clusters resize zenml-kai-cluster \
  --node-pool=default-pool \
  --num-nodes=2 \
  --zone=us-central1-a \
  --project=zenml-core \
  --quiet

# Scale up gpu-pool back to 1 node
echo "Scaling up gpu-pool to 1 node..."
gcloud container clusters resize zenml-kai-cluster \
  --node-pool=gpu-pool \
  --num-nodes=1 \
  --zone=us-central1-a \
  --project=zenml-core \
  --quiet

echo "Waiting for nodes to become available..."
kubectl wait --for=condition=Ready nodes --all --timeout=300s

echo "GKE cluster node pools have been scaled up"
kubectl get nodes