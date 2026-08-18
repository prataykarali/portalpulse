"""Week 1 Multi-Layer Perceptron (MLP) architecture in PyTorch."""

from __future__ import annotations

import torch
import torch.nn as nn


class PortalPulseMLP(nn.Module):
    """Configurable Multi-Layer Perceptron for system telemetry prediction."""

    def __init__(
        self,
        in_features: int = 6,
        hidden_dims: tuple[int, ...] = (64, 32),
        out_features: int = 3,
        activation: str = "relu",
    ) -> None:
        super().__init__()
        self.in_features = in_features
        self.out_features = out_features
        self.activation_name = activation.lower()

        # Resolve activation module
        if self.activation_name == "relu":
            act_cls = nn.ReLU
        elif self.activation_name == "sigmoid":
            act_cls = nn.Sigmoid
        elif self.activation_name == "tanh":
            act_cls = nn.Tanh
        elif self.activation_name == "leaky_relu":
            act_cls = nn.LeakyReLU
        else:
            raise ValueError(f"Unsupported activation: {activation}")

        layers: list[nn.Module] = []
        curr_dim = in_features
        for h_dim in hidden_dims:
            layers.append(nn.Linear(curr_dim, h_dim))
            layers.append(act_cls())
            curr_dim = h_dim

        # Final projection to outputs (linear regression head)
        layers.append(nn.Linear(curr_dim, out_features))
        self.network = nn.Sequential(*layers)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.network(x)
