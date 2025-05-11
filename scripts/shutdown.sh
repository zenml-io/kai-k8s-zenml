#!/bin/bash
set -e

echo "Starting scale-down of GKE cluster node pools"

# Scale down gpu-pool to 0 nodes first (since it has GPUs)
echo "Scaling down gpu-pool to 0 nodes..."
gcloud container clusters resize zenml-kai-cluster \
  --node-pool=gpu-pool \
  --num-nodes=0 \
  --zone=us-central1-a \
  --project=zenml-core \
  --quiet

# Scale down default-pool to 0 nodes
echo "Scaling down default-pool to 0 nodes..."
gcloud container clusters resize zenml-kai-cluster \
  --node-pool=default-pool \
  --num-nodes=0 \
  --zone=us-central1-a \
  --project=zenml-core \
  --quiet

echo "GKE cluster node pools have been scaled down to 0"