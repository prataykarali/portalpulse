"""PyTorch Deep Multi-Layer Perceptron (MLP) Policy Network for Action Intelligence.

Implements the deep policy neural network that maps a 13-dimensional unified system state
vector into a calibrated softmax probability distribution over 11 tactical SRE actions.
Hardware-accelerated on NVIDIA CUDA (GeForce RTX 2050) with CPU fallback.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Union, cast

import torch
import torch.nn as nn
import torch.nn.functional as F

DEFAULT_MODEL_PATH = Path(__file__).resolve().parent / "models" / "action_mlp_policy.pt"


def get_device() -> torch.device:
    """Detect and select the best available compute hardware."""
    if torch.cuda.is_available():
        return torch.device("cuda")
    return torch.device("cpu")


class ActionPolicyMLP(nn.Module):
    """Deep Multi-Layer Perceptron policy network with Batch Normalization and Dropout."""

    def __init__(
        self,
        input_dim: int = 13,
        hidden_dims: Tuple[int, ...] = (128, 256, 128, 64),
        output_dim: int = 11,
        dropout_rates: Tuple[float, ...] = (0.20, 0.25, 0.15),
    ) -> None:
        super().__init__()
        self.input_dim = input_dim
        self.output_dim = output_dim

        # Block 1: 13 -> 128
        self.fc1 = nn.Linear(input_dim, hidden_dims[0])
        self.bn1 = nn.BatchNorm1d(hidden_dims[0])
        self.drop1 = nn.Dropout(dropout_rates[0])

        # Block 2: 128 -> 256
        self.fc2 = nn.Linear(hidden_dims[0], hidden_dims[1])
        self.bn2 = nn.BatchNorm1d(hidden_dims[1])
        self.drop2 = nn.Dropout(dropout_rates[1])

        # Block 3: 256 -> 128
        self.fc3 = nn.Linear(hidden_dims[1], hidden_dims[2])
        self.bn3 = nn.BatchNorm1d(hidden_dims[2])
        self.drop3 = nn.Dropout(dropout_rates[2])

        # Block 4: 128 -> 64
        self.fc4 = nn.Linear(hidden_dims[2], hidden_dims[3])
        self.bn4 = nn.BatchNorm1d(hidden_dims[3])

        # Output Head: 64 -> 11
        self.out_head = nn.Linear(hidden_dims[3], output_dim)

        # Initialize weights with Kaiming He normal
        self._initialize_weights()

    def _initialize_weights(self) -> None:
        """Apply Kaiming He normal initialization to linear layers."""
        for m in self.modules():
            if isinstance(m, nn.Linear):
                nn.init.kaiming_normal_(m.weight, mode="fan_in", nonlinearity="relu")
                if m.bias is not None:
                    nn.init.constant_(m.bias, 0.0)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Compute unnormalized logit scores across 11 discrete actions.

        Args:
            x: Input tensor of shape (batch_size, 13).

        Returns:
            Logit tensor of shape (batch_size, 11).
        """
        # Single sample batch norm handling: if batch size == 1, evaluate in eval mode
        if x.dim() == 1:
            x = x.unsqueeze(0)

        h = F.relu(self.bn1(self.fc1(x)))
        h = self.drop1(h)

        h = F.relu(self.bn2(self.fc2(h)))
        h = self.drop2(h)

        h = F.relu(self.bn3(self.fc3(h)))
        h = self.drop3(h)

        h = F.relu(self.bn4(self.fc4(h)))
        logits = self.out_head(h)
        return cast(torch.Tensor, logits)

    @torch.no_grad()
    def predict_proba(self, x: torch.Tensor) -> torch.Tensor:
        """Compute calibrated softmax probabilities over actions."""
        self.eval()
        if x.dim() == 1:
            x = x.unsqueeze(0)
        # In eval mode with batch_size 1, batchnorm uses running stats
        logits = self.forward(x)
        return F.softmax(logits, dim=-1)

    def save_checkpoint(self, path: Union[str, Path], extra_metadata: Optional[Dict[str, Any]] = None) -> None:
        """Save model state dictionary, architecture hyperparams, and metadata."""
        target_path = Path(path)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "state_dict": self.state_dict(),
            "input_dim": self.input_dim,
            "output_dim": self.output_dim,
            "metadata": extra_metadata or {},
        }
        torch.save(payload, target_path)

    @classmethod
    def load_checkpoint(cls, path: Union[str, Path], map_location: Optional[torch.device] = None) -> Tuple[ActionPolicyMLP, Dict[str, Any]]:
        """Load trained policy model from serialized checkpoint."""
        target_path = Path(path)
        if not target_path.exists():
            raise FileNotFoundError(f"Model checkpoint not found at: {target_path}")

        loc = map_location or get_device()
        payload = torch.load(target_path, map_location=loc, weights_only=False)
        model = cls(input_dim=payload["input_dim"], output_dim=payload["output_dim"])
        model.load_state_dict(payload["state_dict"])
        model.to(loc)
        model.eval()
        return model, payload.get("metadata", {})
