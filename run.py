"""
Main pipeline for training a PyTorch model on the Iris dataset with GPU acceleration and resource monitoring.
"""

import os
import random
import subprocess
import time
import uuid
from typing import Annotated, Tuple

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
import wandb
from sklearn.datasets import load_iris
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from torch.utils.data import DataLoader, TensorDataset
from zenml import pipeline, step
from zenml.types import HTMLString
from zenml.logger import get_logger
from zenml import log_metadata

# Import from our custom modules
from config import docker_settings, kubernetes_settings
from models import IrisModel
from monitoring import ResourceMonitor
from utils import has_cuda_gpu, print_gpu_diagnostics


class WandBCallback:
    """Callback class for WandB logging during PyTorch training."""
    
    def __init__(self, job_id=None):
        self.job_id = job_id or str(uuid.uuid4())[:8]
        
    def on_train_start(self, model, config=None):
        """Log training start info to existing WandB run."""
        # Update config in the existing WandB run
        if config:
            wandb.config.update(config)
        
        # Watch model for gradients and parameters
        wandb.watch(model, log="all")
        
        # Log WandB run URL to ZenML metadata
        if wandb.run:
            wandb_url = wandb.run.get_url()
            log_metadata({"wandb_run_url": wandb_url})
        
    def on_batch_end(self, epoch, batch_idx, loss):
        """Log batch metrics."""
        wandb.log({
            "batch_loss": loss,
            "epoch": epoch,
            "batch": batch_idx
        })
        
    def on_epoch_end(self, epoch, avg_loss, optimizer):
        """Log epoch metrics."""
        wandb.log({
            "epoch_loss": avg_loss,
            "epoch": epoch,
            "learning_rate": optimizer.param_groups[0]['lr']
        })
        
    def on_train_end(self, train_acc, test_acc, train_samples, test_samples, monitor=None):
        """Log final metrics."""
        metrics = {
            "final_train_accuracy": train_acc,
            "final_test_accuracy": test_acc,
            "training_samples": train_samples,
            "test_samples": test_samples
        }
        
        # Add monitoring metrics if available
        if monitor and monitor.timestamps:
            metrics.update({
                "monitoring_duration": monitor.timestamps[-1],
                "data_points_collected": len(monitor.timestamps)
            })
            
            if monitor.cpu_usage:
                metrics["avg_cpu_usage"] = sum(monitor.cpu_usage) / len(monitor.cpu_usage)
            if monitor.gpu_usage:
                metrics["avg_gpu_usage"] = sum(monitor.gpu_usage) / len(monitor.gpu_usage)
                
        wandb.log(metrics)


@step(name="load_iris_dataset")
def load_iris_dataset() -> tuple[
    torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor
]:
    """
    Load, preprocess, and split the Iris dataset into training and testing sets.
    Expand the dataset to make training more GPU-intensive.

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

    # Expand the dataset by duplicating it multiple times to make training more intensive
    expansion_factor = 100  # Reduced from 1000 to make training faster
    X_expanded = np.tile(X, (expansion_factor, 1))
    y_expanded = np.tile(y, expansion_factor)
    
    # Add some noise to make each sample slightly different
    noise = np.random.normal(0, 0.01, X_expanded.shape)
    X_expanded = X_expanded + noise

    print(f"Expanded dataset from {len(X)} to {len(X_expanded)} samples")

    # Split data into train and test sets
    X_train, X_test, y_train, y_test = train_test_split(
        X_expanded, y_expanded, test_size=0.2, random_state=42
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


@step(name="train_iris_model", settings={"orchestrator": kubernetes_settings}, experiment_tracker="wandb")
def train_model_with_gpu(
    X_train_tensor: torch.Tensor,
    X_test_tensor: torch.Tensor,
    y_train_tensor: torch.Tensor,
    y_test_tensor: torch.Tensor,
) -> Tuple[
    Annotated[nn.Module, "trained_model"],
    Annotated[HTMLString, "resource_utilization_chart"]
]:
    """
    Train a PyTorch model on the Iris dataset using GPU if available.
    
    Also monitors CPU and GPU utilization during training and returns
    an HTML visualization of resource usage.

    Args:
        X_train_tensor: Training features as PyTorch tensor
        X_test_tensor: Testing features as PyTorch tensor
        y_train_tensor: Training labels as PyTorch tensor
        y_test_tensor: Testing labels as PyTorch tensor

    Returns:
        Tuple containing:
        - trained_model: Trained PyTorch neural network model
        - resource_utilization_chart: HTML visualization of resource utilization during training
    """
    # Print environment for debugging
    print("\nPreparing to train PyTorch model on Iris dataset...")
    print(f"Current working directory: {os.getcwd()}")
    
    # Add unique job identifier for monitoring
    job_id = str(uuid.uuid4())[:8]  # Short unique identifier
    print(f"Job ID: {job_id}")
    
    # Set job ID as environment variable for visualization
    os.environ['JOB_ID'] = job_id
    
    # Initialize WandB callback
    wandb_callback = WandBCallback(job_id=job_id)
    
    # Add small random delay to stagger dual jobs for more interesting monitoring
    startup_delay = random.uniform(1, 5)  # 1-5 second delay
    print(f"Startup delay: {startup_delay:.1f}s (for dual-job demonstration)")
    time.sleep(startup_delay)
    
    # Initialize resource monitor
    monitor = ResourceMonitor(interval=0.5)
    print(f"GPU monitoring method: {monitor.gpu_monitoring_method}")
    print(f"GPU monitoring available: {monitor.gpu_available}")
    
    # Add GPU diagnostic information
    print_gpu_diagnostics()

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

    # Training parameters
    batch_size = 64
    learning_rate = 0.001
    epochs = 50
    expansion_factor = 100
    
    # Create dataset and dataloader
    train_dataset = TensorDataset(X_train_tensor, y_train_tensor)
    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)

    # Initialize model
    model = IrisModel()
    model.to(device)
    
    # Print model complexity
    total_params = sum(p.numel() for p in model.parameters())
    print(f"Model has {total_params:,} parameters")

    # Define loss function and optimizer
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(model.parameters(), lr=learning_rate)
    
    # Initialize WandB callback with training configuration
    config = {
        "epochs": epochs,
        "batch_size": batch_size,
        "learning_rate": learning_rate,
        "expansion_factor": expansion_factor,
        "total_parameters": total_params
    }
    
    if device.type == "cuda":
        config.update({
            "cuda_device": torch.cuda.get_device_name(0),
            "cuda_device_count": torch.cuda.device_count(),
            "cuda_version": torch.version.cuda
        })
    
    wandb_callback.on_train_start(model, config)

    # Start monitoring before training
    print("Starting resource monitoring...")
    monitor.start_monitoring()

    # Training loop with more epochs and GPU-intensive operations
    print(f"Starting training for {epochs} epochs...")
    
    for epoch in range(epochs):
        model.train()
        running_loss = 0.0
        epoch_losses = []
        
        for batch_idx, (inputs, labels) in enumerate(train_loader):
            optimizer.zero_grad()
            outputs = model(inputs)
            loss = criterion(outputs, labels)
            loss.backward()
            optimizer.step()
            running_loss += loss.item()
            epoch_losses.append(loss.item())
            
            # Log batch loss via callback
            wandb_callback.on_batch_end(epoch, batch_idx, loss.item())
            
            # Add GPU-intensive operations every 10 batches (increased frequency)
            if batch_idx % 10 == 0:  # Every 10th batch instead of 20th
                with torch.no_grad():
                    # Create larger dummy GPU computations
                    dummy_matrix1 = torch.randn(512, 512, device=device)  # Increased from 256x256
                    dummy_matrix2 = torch.randn(512, 512, device=device)
                    dummy_matrix3 = torch.randn(512, 512, device=device)
                    
                    # Perform more intensive matrix operations
                    for _ in range(5):  # Increased from 2 to 5 iterations
                        dummy_result = torch.mm(dummy_matrix1, dummy_matrix2)
                        dummy_result = torch.mm(dummy_result, dummy_matrix3)
                        dummy_result = torch.nn.functional.relu(dummy_result)
                        dummy_result = torch.tanh(dummy_result)  # Additional activation
                        
                        # Add some convolution-like operations for extra GPU load
                        conv_input = dummy_result.unsqueeze(0).unsqueeze(0)  # Add batch and channel dims
                        conv_result = torch.nn.functional.conv2d(
                            conv_input, 
                            torch.randn(16, 1, 3, 3, device=device),  # 16 filters, 3x3 kernel
                            padding=1
                        )
                        conv_result = torch.nn.functional.max_pool2d(conv_result, 2)
                    
                    # Force GPU synchronization to ensure operations complete
                    if device.type == "cuda":
                        torch.cuda.synchronize()

        # Add intensive GPU operations more frequently
        if epoch % 5 == 0:  # Every 5th epoch instead of 10th
            with torch.no_grad():
                print(f"Epoch {epoch + 1}/{epochs} - Adding intensive GPU operations...")
                
                # Create even larger matrices for maximum GPU stress
                large_matrix1 = torch.randn(1024, 1024, device=device)  # Increased from 512x512
                large_matrix2 = torch.randn(1024, 1024, device=device)
                large_matrix3 = torch.randn(1024, 1024, device=device)
                
                # Perform many intensive operations
                for _ in range(8):  # Increased from 3 to 8 iterations
                    intensive_result = torch.mm(large_matrix1, large_matrix2)
                    intensive_result = torch.mm(intensive_result, large_matrix3)
                    intensive_result = torch.sin(intensive_result)
                    intensive_result = torch.cos(intensive_result)
                    intensive_result = torch.exp(torch.clamp(intensive_result, -1, 1))
                    
                    # Add eigenvalue decomposition for extra computational load
                    try:
                        # Eigenvalue decomposition is very GPU-intensive
                        small_matrix = intensive_result[:64, :64]  # Take smaller subset for stability
                        _ = torch.linalg.eigvals(small_matrix + small_matrix.T)  # Make symmetric
                    except:
                        pass  # Skip if eigenvalue computation fails
                    
                    # Additional matrix chain operations
                    _ = torch.chain_matmul(large_matrix1[:256, :256], 
                                         large_matrix2[:256, :256], 
                                         large_matrix3[:256, :256])
                
                # Force GPU synchronization
                if device.type == "cuda":
                    torch.cuda.synchronize()
            
            avg_epoch_loss = running_loss / len(train_loader)
            print(f"Epoch {epoch + 1}/{epochs}, Loss: {avg_epoch_loss:.4f}")
        elif (epoch + 1) % 3 == 0:  # Show progress every 3 epochs instead of 5
            avg_epoch_loss = running_loss / len(train_loader)
            print(f"Epoch {epoch + 1}/{epochs}, Loss: {avg_epoch_loss:.4f}")
        
        # Always call epoch callback for every epoch
        avg_epoch_loss = running_loss / len(train_loader)
        wandb_callback.on_epoch_end(epoch + 1, avg_epoch_loss, optimizer)

    # Stop monitoring after training
    print("Stopping resource monitoring...")
    monitor.stop_monitoring()
    
    # Give the monitor a moment to collect final data
    time.sleep(1)

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
    
    # Log final metrics via callback
    wandb_callback.on_train_end(
        train_acc.item(), 
        test_acc.item(), 
        len(X_train_tensor), 
        len(X_test_tensor),
        monitor
    )
    
    # Log key metrics to ZenML metadata for dashboard comparison
    performance_metrics = {
        "train_accuracy": train_acc.item(),
        "test_accuracy": test_acc.item(),
        "final_train_loss": running_loss / len(train_loader)
    }
    
    training_config = {
        "epochs": epochs,
        "batch_size": batch_size,
        "learning_rate": learning_rate,
        "device": str(device),
        "total_parameters": total_params
    }
    
    resource_metrics = {}
    if monitor and monitor.timestamps:
        resource_metrics = {
            "training_duration_seconds": monitor.timestamps[-1],
            "avg_cpu_usage_percent": sum(monitor.cpu_usage) / len(monitor.cpu_usage) if monitor.cpu_usage else 0,
            "avg_gpu_usage_percent": sum(monitor.gpu_usage) / len(monitor.gpu_usage) if monitor.gpu_usage else 0
        }
    
    # Log structured metadata to ZenML
    log_metadata({
        "performance": performance_metrics,
        "training_config": training_config,
        "resources": resource_metrics,
        "job_id": job_id
    })
    
    # Generate HTML visualization
    print("Generating resource utilization visualization...")
    html_viz = monitor.generate_html_visualization()
    
    # Print monitoring summary
    if monitor.timestamps:
        print(f"Monitoring duration: {monitor.timestamps[-1]:.1f} seconds")
        print(f"Data points collected: {len(monitor.timestamps)}")
        if monitor.cpu_usage:
            print(f"Average CPU usage: {sum(monitor.cpu_usage)/len(monitor.cpu_usage):.1f}%")
        if monitor.gpu_usage:
            avg_gpu_usage = sum(monitor.gpu_usage)/len(monitor.gpu_usage)
            print(f"Average GPU usage: {avg_gpu_usage:.1f}%")

    return model, HTMLString(html_viz)


@pipeline(
    name="gpu_pipeline",
    settings={"docker": docker_settings},
    enable_cache=False,
)
def gpu_test_pipeline():
    """GPU-accelerated pipeline for training a PyTorch model on the Iris dataset."""
    # Load and preprocess the Iris dataset
    X_train, X_test, y_train, y_test = load_iris_dataset()

    # Train the model using GPU acceleration and get resource monitoring visualization
    trained_model, resource_utilization_chart = train_model_with_gpu(X_train, X_test, y_train, y_test)
    
    # The trained_model and resource_utilization_chart are now available as separate named artifacts
    # The visualization will be displayed in the ZenML dashboard with the name "resource_utilization_chart"


if __name__ == "__main__":
    gpu_test_pipeline()
