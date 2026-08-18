"""Week 2 Experiment: Regularization & Dropout (Overfitting analysis)."""

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


def run_reg_experiment(dropout_p: float, weight_decay: float, label: str, epochs: int = 25, lr: float = 0.005) -> dict:
    train_loader, val_loader, test_loader, scaler = load_dataloaders(batch_size=128)
    model = AdvancedMultiOutputMLP(
        in_features=6,
        hidden_dims=(128, 64, 32),
        out_features=3,
        use_batchnorm=True,
        dropout_p=dropout_p,
        init_type="he",
    )
    criterion = nn.MSELoss()
    optimizer = optim.Adam(model.parameters(), lr=lr, weight_decay=weight_decay)

    train_losses = []
    val_losses = []

    t0 = time.perf_counter()
    for epoch in range(epochs):
        model.train()
        running_train = 0.0
        for X_b, y_b in train_loader:
            optimizer.zero_grad()
            preds = model(X_b)
            loss = criterion(preds, y_b)
            loss.backward()
            optimizer.step()
            running_train += loss.item() * len(X_b)

        train_loss = running_train / len(train_loader.dataset)
        train_losses.append(round(train_loss, 4))

        model.eval()
        running_val = 0.0
        with torch.no_grad():
            for X_v, y_v in val_loader:
                v_preds = model(X_v)
                v_loss = criterion(v_preds, y_v)
                running_val += v_loss.item() * len(X_v)

        val_loss = running_val / len(val_loader.dataset)
        val_losses.append(round(val_loss, 4))

    elapsed = round(time.perf_counter() - t0, 2)

    model.eval()
    all_preds, all_targets = [], []
    with torch.no_grad():
        for X_t, y_t in test_loader:
            all_preds.append(model(X_t).numpy())
            all_targets.append(y_t.numpy())

    preds_scaled = np.vstack(all_preds)
    targets_scaled = np.vstack(all_targets)
    preds_raw = scaler.inverse_transform_y(preds_scaled)
    targets_raw = scaler.inverse_transform_y(targets_scaled)

    mae_per_target = np.mean(np.abs(preds_raw - targets_raw), axis=0)

    return {
        "variant": label,
        "dropout_p": dropout_p,
        "weight_decay": weight_decay,
        "final_train_loss_mse": train_losses[-1],
        "final_val_loss_mse": val_losses[-1],
        "test_mae_safe_capacity": round(float(mae_per_target[2]), 2),
        "generalization_gap": round(val_losses[-1] - train_losses[-1], 4),
        "training_time_sec": elapsed,
        "train_loss_history": train_losses,
        "val_loss_history": val_losses,
    }


def main() -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    configs = [
        {"dropout_p": 0.0, "weight_decay": 0.0, "label": "No Regularization (Baseline)"},
        {"dropout_p": 0.20, "weight_decay": 0.0, "label": "With Dropout (p=0.2)"},
        {"dropout_p": 0.15, "weight_decay": 1e-4, "label": "Dropout (0.15) + L2 Weight Decay"},
    ]
    results = []

    print("Running Week 2 Dropout & Regularization Experiments...")
    for cfg in configs:
        res = run_reg_experiment(cfg["dropout_p"], cfg["weight_decay"], cfg["label"])
        results.append(res)
        print(f"[{res['variant']}] Val MSE: {res['final_val_loss_mse']} | Gen Gap: {res['generalization_gap']} | Capacity MAE: {res['test_mae_safe_capacity']} users")

    out_file = RESULTS_DIR / "dropout_regularization_experiments.json"
    out_file.write_text(json.dumps(results, indent=2) + "\n")
    print(f"\nSaved Regularization report to: {out_file}")


if __name__ == "__main__":
    main()
