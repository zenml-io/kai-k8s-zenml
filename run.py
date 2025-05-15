import ctypes
import os
import subprocess
from ctypes import byref, c_int

import torch
import torch.nn as nn
import torch.optim as optim
from kubernetes.client.models import V1Toleration
from sklearn.datasets import load_iris
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from torch.utils.data import DataLoader, TensorDataset
from zenml import pipeline, step
from zenml.config import DockerSettings
from zenml.integrations.kubernetes.flavors.kubernetes_orchestrator_flavor import (
    KubernetesOrchestratorSettings,
)

# Use custom Dockerfile with PyTorch and CUDA support
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
        # Using standard GKE device plugin instead of NVIDIA runtime
        # "runtime_class_name": "nvidia",
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


def has_cuda_gpu() -> bool:
    """
    Check if CUDA GPU is available using multiple detection methods.

    Returns:
        bool: True if a CUDA GPU is available, False otherwise
    """
    # For KAI Scheduler first check environment variables set by the scheduler
    if "NVIDIA_VISIBLE_DEVICES" in os.environ or "RUNAI-VISIBLE-DEVICES" in os.environ:
        devices = os.environ.get(
            "NVIDIA_VISIBLE_DEVICES", os.environ.get("RUNAI-VISIBLE-DEVICES", "")
        )
        if devices and devices != "-1" and devices != "void":
            print(f"Found GPU via KAI Scheduler environment: {devices}")
            return True

    # Method 1: Check standard CUDA environment variables
    if any(var in os.environ for var in ["CUDA_VISIBLE_DEVICES", "GPU_DEVICE_ORDINAL"]):
        devices = os.environ.get(
            "CUDA_VISIBLE_DEVICES", os.environ.get("GPU_DEVICE_ORDINAL", "")
        )
        if devices and devices != "-1":
            print(f"Found GPU via CUDA_VISIBLE_DEVICES/GPU_DEVICE_ORDINAL: {devices}")
            return True

    # Method 2: Check for CDI environment (Container Device Interface)
    if os.path.exists("/etc/cdi"):
        print("Found /etc/cdi directory - CDI configuration present")
        return True

    # Method 3: Try CUDA driver detection via ctypes
    for lib in ("libcuda.so", "libcuda.so.1", "libcuda.dylib", "nvcuda.dll"):
        try:
            cuda = ctypes.CDLL(lib)
            # Initialize the driver
            result = cuda.cuInit(0)
            if result == 0:  # Success
                # Get device count
                count = c_int()
                if cuda.cuDeviceGetCount(byref(count)) == 0:  # Success
                    if count.value > 0:
                        print(f"Found GPU via CUDA API: {count.value} device(s)")
                        return True
        except (OSError, AttributeError):
            # Library not found or missing required function
            continue

    # Method 4: Check using subprocess (nvidia-smi)
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=5,  # Add timeout to prevent hanging
        )
        if result.returncode == 0 and result.stdout.strip():
            print(f"Found GPU via nvidia-smi: {result.stdout.strip()}")
            return True
    except (subprocess.SubprocessError, FileNotFoundError):
        # nvidia-smi not available or failed
        pass

    # Debug info to help diagnose issues
    print("Environment variables:")
    for var in [
        "NVIDIA_VISIBLE_DEVICES",
        "RUNAI-VISIBLE-DEVICES",
        "CUDA_VISIBLE_DEVICES",
        "GPU_DEVICE_ORDINAL",
        "NVIDIA_DRIVER_CAPABILITIES",
        "RUNAI_NUM_OF_GPUS",
    ]:
        if var in os.environ:
            print(f"  {var}={os.environ[var]}")

    # No GPU detected with any method
    return False


# Define a simple PyTorch model for Iris classification
class IrisModel(nn.Module):
    def __init__(self, input_size=4, hidden_size=10, num_classes=3):
        super(IrisModel, self).__init__()
        self.layer1 = nn.Linear(input_size, hidden_size)
        self.relu = nn.ReLU()
        self.layer2 = nn.Linear(hidden_size, num_classes)

    def forward(self, x):
        x = self.layer1(x)
        x = self.relu(x)
        x = self.layer2(x)
        return x


@step(name="load_iris_dataset")
def load_iris_dataset() -> tuple[
    torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor
]:
    """
    Load, preprocess, and split the Iris dataset into training and testing sets.

    Returns:
        Tuple containing:
        - X_train_tensor: Training features as PyTorch tensor
        - X_test_tensor: Testing features as PyTorch tensor
        - y_train_tensor: Training labels as PyTorch tensor
        - y_test_tensor: Testing labels as PyTorch tensor
    """
    print("Loading and preprocessing Iris dataset...")

    # Load dataset
    X, y = load_iris(return_X_y=True)

    # Split data into train and test sets
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    # Standardize features
    scaler = StandardScaler()
    X_train = scaler.fit_transform(X_train)
    X_test = scaler.transform(X_test)

    # Convert to PyTorch tensors
    X_train_tensor = torch.FloatTensor(X_train)
    y_train_tensor = torch.LongTensor(y_train)
    X_test_tensor = torch.FloatTensor(X_test)
    y_test_tensor = torch.LongTensor(y_test)

    print(
        f"Dataset prepared: {len(X_train_tensor)} training samples, {len(X_test_tensor)} testing samples"
    )

    return X_train_tensor, X_test_tensor, y_train_tensor, y_test_tensor


# Define a GPU-enabled step for training PyTorch model on Iris dataset
@step(name="train_iris_model", settings={"orchestrator": kubernetes_settings})
def train_model_with_gpu(
    X_train_tensor: torch.Tensor,
    X_test_tensor: torch.Tensor,
    y_train_tensor: torch.Tensor,
    y_test_tensor: torch.Tensor,
) -> nn.Module:
    """
    Train a PyTorch model on the Iris dataset using GPU if available.

    Args:
        X_train_tensor: Training features as PyTorch tensor
        X_test_tensor: Testing features as PyTorch tensor
        y_train_tensor: Training labels as PyTorch tensor
        y_test_tensor: Testing labels as PyTorch tensor

    Returns:
        Trained PyTorch neural network model
    """
    # Print environment for debugging
    print("\nPreparing to train PyTorch model on Iris dataset...")
    print(f"Current working directory: {os.getcwd()}")

    # Check GPU availability
    gpu_available = has_cuda_gpu()
    print(f"GPU is available: {gpu_available}")
    device = torch.device(
        "cuda" if gpu_available and torch.cuda.is_available() else "cpu"
    )
    print(f"Using device: {device}")

    if device.type == "cuda":
        print(f"CUDA Device: {torch.cuda.get_device_name(0)}")
        print(f"CUDA Device Count: {torch.cuda.device_count()}")
        print(f"CUDA Version: {torch.version.cuda}")

    # Move data to device
    X_train_tensor = X_train_tensor.to(device)
    y_train_tensor = y_train_tensor.to(device)
    X_test_tensor = X_test_tensor.to(device)
    y_test_tensor = y_test_tensor.to(device)

    # Create dataset and dataloader
    train_dataset = TensorDataset(X_train_tensor, y_train_tensor)
    train_loader = DataLoader(train_dataset, batch_size=8, shuffle=True)

    # Initialize model
    model = IrisModel()
    model.to(device)

    # Define loss function and optimizer
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(model.parameters(), lr=0.001)

    # Training loop
    epochs = 100
    for epoch in range(epochs):
        model.train()
        running_loss = 0.0

        for inputs, labels in train_loader:
            optimizer.zero_grad()
            outputs = model(inputs)
            loss = criterion(outputs, labels)
            loss.backward()
            optimizer.step()
            running_loss += loss.item()

        if (epoch + 1) % 20 == 0:
            print(
                f"Epoch {epoch + 1}/{epochs}, Loss: {running_loss / len(train_loader):.4f}"
            )

    # Evaluate model
    model.eval()
    with torch.no_grad():
        train_outputs = model(X_train_tensor)
        _, train_preds = torch.max(train_outputs, 1)
        train_acc = (train_preds == y_train_tensor).float().mean()

        test_outputs = model(X_test_tensor)
        _, test_preds = torch.max(test_outputs, 1)
        test_acc = (test_preds == y_test_tensor).float().mean()

    print(f"\nTraining complete!")
    print(f"Train accuracy: {train_acc.item():.4f}")
    print(f"Test accuracy: {test_acc.item():.4f}")

    return model


# Use shorter pipeline name
@pipeline(
    name="gpu_pipeline",
    settings={"docker": docker_settings},
    enable_cache=False,
)
def gpu_test_pipeline():
    """GPU-accelerated pipeline for training a PyTorch model on the Iris dataset."""
    # Load and preprocess the Iris dataset
    X_train, X_test, y_train, y_test = load_iris_dataset()

    # Train the model using GPU acceleration
    train_model_with_gpu(X_train, X_test, y_train, y_test)


if __name__ == "__main__":
    gpu_test_pipeline()
