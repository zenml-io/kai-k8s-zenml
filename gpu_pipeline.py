import ctypes
from ctypes import byref, c_int

from kubernetes.client.models import V1Toleration
from zenml import pipeline, step
from zenml.config import DockerSettings
from zenml.integrations.kubernetes.flavors.kubernetes_orchestrator_flavor import (
    KubernetesOrchestratorSettings,
)

# Use a custom Dockerfile that includes Python, pip, and ZenML
docker_settings = DockerSettings(python_package_installer="uv")

# Define Kubernetes settings for GPU resources using the KubernetesOrchestratorSettings
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
    # 1.  Try every name the driver might have on the current OS
    for lib in ("libcuda.so", "libcuda.dylib", "nvcuda.dll"):
        try:
            cuda = ctypes.CDLL(lib)
        except OSError:
            continue  # library not found on this platform – keep trying
        # 2.  Probe the driver
        if cuda.cuInit(0) != 0:  # driver present but not initialised
            continue
        count = c_int()
        if cuda.cuDeviceGetCount(byref(count)) != 0:
            continue  # API failed – treat as “no GPU”
        return count.value > 0
    return False  # no driver library found at all


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
