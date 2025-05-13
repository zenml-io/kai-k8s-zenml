import ctypes
import os
import subprocess
from ctypes import byref, c_int

from kubernetes.client.models import V1Toleration
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


# Define a GPU-enabled step with a shorter name
@step(name="gpu_step", settings={"orchestrator": kubernetes_settings})
def gpu_test_step() -> None:
    try:
        # Print environment for debugging
        print("\nChecking for GPU access in KAI Scheduler environment...")
        print(f"Current working directory: {os.getcwd()}")

        # Check if we have /dev/nvidia* devices
        try:
            nvidia_devices = [d for d in os.listdir("/dev") if d.startswith("nvidia")]
            if nvidia_devices:
                print(f"Found nvidia devices in /dev: {', '.join(nvidia_devices)}")
            else:
                print("No nvidia devices found in /dev directory")
        except Exception as e:
            print(f"Error checking /dev for nvidia devices: {e}")

        # Try to run nvidia-smi to verify GPU access
        try:
            # Try direct nvidia-smi command
            nvidia_result = subprocess.run(
                ["nvidia-smi"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=5,
            )
            if nvidia_result.returncode == 0:
                print("\nnvidia-smi output:\n" + nvidia_result.stdout)
            else:
                print(f"nvidia-smi failed with error: {nvidia_result.stderr}")
        except Exception as e:
            print(f"Failed to run nvidia-smi: {e}")

        # Try our comprehensive GPU detection
        output = has_cuda_gpu()
        print(f"\nGPU is available: {output}")
    except Exception as e:
        print(f"Error accessing GPU: {e}")
        import traceback

        traceback.print_exc()


# Use shorter pipeline name
@pipeline(
    name="gpu_pipeline",
    settings={"docker": docker_settings},
    enable_cache=False,
)
def gpu_test_pipeline():
    gpu_test_step()


if __name__ == "__main__":
    gpu_test_pipeline()
