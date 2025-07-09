"""
PyTorch model definitions for the Iris classification task.
"""

import torch
import torch.nn as nn


class IrisModel(nn.Module):
    """A moderately complex neural network for Iris classification that utilizes GPU efficiently."""
    
    def __init__(self, input_size: int = 4, hidden_sizes: list = None, num_classes: int = 3):
        super(IrisModel, self).__init__()
        
        if hidden_sizes is None:
            hidden_sizes = [64, 128, 64]  # Default architecture
        
        # Create a moderately deep network to increase GPU utilization
        layers = []
        prev_size = input_size
        
        for hidden_size in hidden_sizes:
            layers.extend([
                nn.Linear(prev_size, hidden_size),
                nn.ReLU(),
                nn.Dropout(0.1),  # Reduced dropout
                nn.BatchNorm1d(hidden_size)
            ])
            prev_size = hidden_size
        
        # Output layer
        layers.append(nn.Linear(prev_size, num_classes))
        
        self.network = nn.Sequential(*layers)
        
        # Simplified additional layers for moderate GPU usage
        self.extra_computation = nn.Sequential(
            nn.Linear(hidden_sizes[-1], hidden_sizes[-1]),
            nn.ReLU(),
            nn.Linear(hidden_sizes[-1], hidden_sizes[-1])
        )

    def forward(self, x):
        # Pass through main network
        features = self.network[:-1](x)  # All layers except the last
        
        # Add moderate GPU computation
        enhanced_features = self.extra_computation(features)
        
        # Combine features
        combined_features = features + enhanced_features
        
        # Final output layer
        output = self.network[-1](combined_features)
        
        return output 