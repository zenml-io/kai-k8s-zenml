"""
Utility functions for GPU detection and other helper operations.
"""

import ctypes
import os
import subprocess
from ctypes import byref, c_int


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


def print_gpu_diagnostics():
    """Print comprehensive GPU diagnostic information."""
    import torch
    
    print("\n🔍 GPU Diagnostic Information:")
    print(f"PyTorch CUDA available: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"PyTorch CUDA device count: {torch.cuda.device_count()}")
        print(f"Current CUDA device: {torch.cuda.current_device()}")
        print(f"CUDA device name: {torch.cuda.get_device_name(0)}")
    
    # Test nvidia-smi command
    try:
        result = subprocess.run(['nvidia-smi', '--query-gpu=name,utilization.gpu', '--format=csv,noheader'], 
                              capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            print(f"nvidia-smi test: ✅ {result.stdout.strip()}")
        else:
            print(f"nvidia-smi test: ❌ Return code {result.returncode}")
    except Exception as e:
        print(f"nvidia-smi test: ❌ {e}")
    
    print("")  # Empty line for readability 