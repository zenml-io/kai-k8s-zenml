from zenml import pipeline, step
from zenml.integrations.kubernetes.flavors.kubernetes_orchestrator_flavor import (
    KubernetesOrchestratorSettings,
)

# Define KAI Scheduler settings
kai_settings = KubernetesOrchestratorSettings(
    pod_settings={
        # Use KAI Scheduler
        "scheduler_name": "kai-scheduler",
        # Add KAI label for queue
        "labels": {"runai/queue": "test"},
        # Request GPU resources
        "resources": {"limits": {"nvidia.com/gpu": "1"}},
        # Add toleration for GPU nodes
        "tolerations": [
            {
                "key": "nvidia.com/gpu",
                "operator": "Equal",
                "value": "present",
                "effect": "NoSchedule",
            }
        ],
    },
    kubernetes_namespace="zenml",
)


# Define a GPU-enabled step
@step(settings={"orchestrator": kai_settings})
def gpu_test_step() -> None:
    import subprocess

    try:
        # Try to run nvidia-smi to verify GPU access
        output = subprocess.check_output(["nvidia-smi"])
        print(f"GPU is available:\n{output.decode()}")
    except Exception as e:
        print(f"Error accessing GPU: {e}")


# Define a simple pipeline
@pipeline
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
