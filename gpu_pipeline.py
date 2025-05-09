from zenml import pipeline, step
from zenml.config import DockerSettings
import os

# Get the current directory to build the Dockerfile with the correct path
current_dir = os.path.dirname(os.path.abspath(__file__))
dockerfile_path = os.path.join(current_dir, "Dockerfile.gpu")

# Use a custom Dockerfile that includes Python, pip, and ZenML
docker_settings = DockerSettings(
    dockerfile=dockerfile_path,
    package_installer="uv",
    # parent_image="nvidia/cuda:12.2.0-runtime-ubuntu22.04",
    apt_packages=["python3-pip", "python3-dev", "python-is-python3"],
    environment={"DEBIAN_FRONTEND": "noninteractive"},
)


# Define a GPU-enabled step with a shorter name
@step(name="gpu_step")
def gpu_test_step() -> None:
    import subprocess

    try:
        # Try to run nvidia-smi to verify GPU access
        output = subprocess.check_output(["nvidia-smi"])
        print(f"GPU is available:\n{output.decode()}")
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
