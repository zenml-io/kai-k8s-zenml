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
docker_settings = DockerSettings(
    dockerfile="/Users/strickvl/coding/zenml/repos/kai-k8s-zenml/Dockerfile.pytorch",
    build_context_root="/Users/strickvl/coding/zenml/repos/kai-k8s-zenml",
    python_package_installer="uv",
)

kubernetes_settings = KubernetesOrchestratorSettings(
    pod_settings={
        "resources": {
            "limits": {"nvidia.com/gpu": "1"},
            "requests": {"nvidia.com/gpu": "1"},
        },
        "tolerations": [
            V1Toleration(
                key="nvidia.com/gpu",
                operator="Equal",
                value="present",
                effect="NoSchedule",
            )
        ],
    }
)


def has_cuda_gpu() -> bool:
    """
    Check if CUDA GPU is available using multiple detection methods.

    Returns:
        bool: True if a CUDA GPU is available, False otherwise
    """
    # Method 1: Check environment variables
    if any(var in os.environ for var in ["CUDA_VISIBLE_DEVICES", "GPU_DEVICE_ORDINAL"]):
        devices = os.environ.get(
            "CUDA_VISIBLE_DEVICES", os.environ.get("GPU_DEVICE_ORDINAL", "")
        )
        if devices and devices != "-1":
            return True

    # Method 2: Try CUDA driver detection via ctypes
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
                        return True
        except (OSError, AttributeError):
            # Library not found or missing required function
            continue

    # Method 3: Check using subprocess (nvidia-smi)
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=5,  # Add timeout to prevent hanging
        )
        if result.returncode == 0 and result.stdout.strip():
            return True
    except (subprocess.SubprocessError, FileNotFoundError):
        # nvidia-smi not available or failed
        pass

    # No GPU detected with any method
    return False


# Define a GPU-enabled step with a shorter name
@step(name="gpu_step", settings={"orchestrator": kubernetes_settings})
def gpu_test_step() -> None:
    try:
        # Try to run nvidia-smi to verify GPU access
        output = has_cuda_gpu()
        print(f"GPU is available: {output}")
    except Exception as e:
        print(f"Error accessing GPU: {e}")


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
