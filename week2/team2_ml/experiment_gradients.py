"""Week 2 Experiment: Explicit Backpropagation & Gradient Flow Analysis.

Demonstrates PyTorch autograd computation graph:
Forward Pass -> Loss Calculation -> loss.backward() -> Layer Gradient Norms -> Optimizer Step.

Compares gradient stability and magnitude across Default, Xavier, and He Normal initializations.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from week1.team1_data.dataset import load_dataloaders
from week2.team2_ml.multi_output_mlp import AdvancedMultiOutputMLP

RESULTS_DIR = ROOT / "week2" / "team2_ml" / "results"


def compute_layer_gradient_norms(model: nn.Module) -> dict[str, float]:
    """Compute Frobenius / L2 norm of weight gradients for each linear layer."""
    norms = {}
    for name, param in model.named_parameters():
        if "weight" in name and param.grad is not None:
            norm_val = float(param.grad.data.norm(2).item())
            clean_name = name.replace(".weight", "")
            norms[clean_name] = round(norm_val, 5)
    return norms


def run_gradient_experiment(init_type: str, epochs: int = 15, lr: float = 0.005) -> dict:
    train_loader, val_loader, _, _ = load_dataloaders(batch_size=128)
    model = AdvancedMultiOutputMLP(
        in_features=6,
        hidden_dims=(128, 64, 32),
        out_features=3,
        use_batchnorm=False,  # Test raw init gradient propagation
        dropout_p=0.0,
        init_type=init_type,
    )
    criterion = nn.MSELoss()
    optimizer = optim.Adam(model.parameters(), lr=lr)

    gradient_history: list[dict] = []
    loss_history: list[float] = []

    print(f"Tracking Gradient Flow for '{init_type.upper()}' Initialization...")

    for epoch in range(1, epochs + 1):
        model.train()
        running_loss = 0.0
        epoch_grad_norms: list[dict[str, float]] = []

        for X_batch, y_batch in train_loader:
            optimizer.zero_grad()  # 1. Clear previous gradients

            # 2. Forward Propagation
            predictions = model(X_batch)

            # 3. Loss Calculation
            loss = criterion(predictions, y_batch)

            # 4. Backward Propagation (Autograd DAG traversal)
            loss.backward()

            # 5. Extract and inspect layer-wise gradient magnitudes
            grad_norms = compute_layer_gradient_norms(model)
            epoch_grad_norms.append(grad_norms)

            # 6. Weight Update
            optimizer.step()
            running_loss += loss.item() * len(X_batch)

        avg_loss = round(running_loss / len(train_loader.dataset), 5)
        loss_history.append(avg_loss)

        # Average layer gradient norms over the epoch batches
        layer_names = epoch_grad_norms[0].keys()
        avg_layer_norms = {
            layer: round(float(np.mean([batch[layer] for batch in epoch_grad_norms])), 5)
            for layer in layer_names
        }
        avg_layer_norms["epoch"] = epoch
        avg_layer_norms["train_loss"] = avg_loss
        gradient_history.append(avg_layer_norms)

    # Compute gradient vanishing/exploding ratio: Layer_1 gradient vs Output Layer gradient
    final_grads = gradient_history[-1]
    first_layer_key = list(final_grads.keys())[0]
    last_layer_key = [k for k in final_grads.keys() if "network" in k][-1]
    flow_ratio = round(final_grads[first_layer_key] / max(final_grads[last_layer_key], 1e-6), 3)

    return {
        "initialization": init_type.upper(),
        "final_train_loss": loss_history[-1],
        "gradient_flow_ratio_in_vs_out": flow_ratio,
        "gradient_history_by_epoch": gradient_history,
    }


def main() -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    inits = ["default", "xavier", "he"]
    results = {}

    print("=================================================================")
    print(" Week 2 Deep Learning Lab: Backpropagation & Gradient Flow Audit ")
    print("=================================================================\n")

    for init_type in inits:
        res = run_gradient_experiment(init_type, epochs=15)
        results[init_type] = res
        print(f"[{res['initialization']}] Final Loss: {res['final_train_loss']} | Grad Ratio (In/Out): {res['gradient_flow_ratio_in_vs_out']}\n")

    out_file = RESULTS_DIR / "gradient_flow_experiments.json"
    out_file.write_text(json.dumps(results, indent=2) + "\n")
    print(f"✓ Saved explicit backpropagation & gradient report to: {out_file}")


if __name__ == "__main__":
    main()
