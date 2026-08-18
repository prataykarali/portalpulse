"""Week 2 Advanced PyTorch Multi-Output MLP with BatchNorm, Dropout, and Custom Init."""

from __future__ import annotations

import torch
import torch.nn as nn


class AdvancedMultiOutputMLP(nn.Module):
    """Shared-representation PyTorch MLP with BatchNorm, Dropout, and multi-head outputs."""

    def __init__(
        self,
        in_features: int = 6,
        hidden_dims: tuple[int, ...] = (128, 64, 32),
        out_features: int = 3,
        use_batchnorm: bool = True,
        dropout_p: float = 0.15,
        init_type: str = "he",
    ) -> None:
        super().__init__()
        self.in_features = in_features
        self.out_features = out_features
        self.use_batchnorm = use_batchnorm
        self.dropout_p = dropout_p

        layers: list[nn.Module] = []
        curr_dim = in_features
        for h_dim in hidden_dims:
            layers.append(nn.Linear(curr_dim, h_dim))
            if use_batchnorm:
                layers.append(nn.BatchNorm1d(h_dim))
            layers.append(nn.ReLU())
            if dropout_p > 0.0:
                layers.append(nn.Dropout(p=dropout_p))
            curr_dim = h_dim

        # Final projection head
        layers.append(nn.Linear(curr_dim, out_features))
        self.network = nn.Sequential(*layers)

        # Apply weight initialization
        self._apply_initialization(init_type)

    def _apply_initialization(self, init_type: str) -> None:
        init_type = init_type.lower()
        for m in self.modules():
            if isinstance(m, nn.Linear):
                if init_type == "xavier":
                    nn.init.xavier_uniform_(m.weight)
                elif init_type == "he":
                    nn.init.kaiming_normal_(m.weight, nonlinearity="relu")
                elif init_type == "default":
                    pass  # PyTorch default uniform
                if m.bias is not None:
                    nn.init.zeros_(m.bias)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.network(x)
