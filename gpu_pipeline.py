import ctypes
import os
from ctypes import byref, c_int

from zenml import pipeline, step
from zenml.config import DockerSettings

# Get the current directory to build the Dockerfile with the correct path
current_dir = os.path.dirname(os.path.abspath(__file__))
dockerfile_path = os.path.join(current_dir, "Dockerfile.gpu")

# Use a custom Dockerfile that includes Python, pip, and ZenML
docker_settings = DockerSettings(python_package_installer="uv")


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
@step(name="gpu_step")
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
    # Get the active stack
    from zenml.client import Client

    client = Client()
    active_stack = client.active_stack

    if active_stack:
        print(f"Using active stack: {active_stack.name}")
        # Run the pipeline with active stack
        gpu_test_pipeline()
    else:
        print("No active stack found.")
        print("Please set up and activate a stack first")
