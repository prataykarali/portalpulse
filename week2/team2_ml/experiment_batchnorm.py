"""Week 2 Experiment: Batch Normalization (With BatchNorm vs Without BatchNorm)."""

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


def run_bn_experiment(use_bn: bool, epochs: int = 25, lr: float = 0.005) -> dict:
    train_loader, val_loader, test_loader, scaler = load_dataloaders(batch_size=128)
    model = AdvancedMultiOutputMLP(
        in_features=6,
        hidden_dims=(128, 64, 32),
        out_features=3,
        use_batchnorm=use_bn,
        dropout_p=0.0,
        init_type="he",
    )
    criterion = nn.MSELoss()
    optimizer = optim.Adam(model.parameters(), lr=lr)

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

    label = "With BatchNorm" if use_bn else "Without BatchNorm"
    return {
        "variant": label,
        "use_batchnorm": use_bn,
        "final_train_loss_mse": train_losses[-1],
        "final_val_loss_mse": val_losses[-1],
        "test_mae_safe_capacity": round(float(mae_per_target[2]), 2),
        "training_time_sec": elapsed,
        "train_loss_history": train_losses,
        "val_loss_history": val_losses,
    }


def main() -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    results = [run_bn_experiment(False), run_bn_experiment(True)]

    print("Running Week 2 Batch Normalization Experiments...")
    for res in results:
        print(f"[{res['variant']}] Val MSE: {res['final_val_loss_mse']} | Safe Capacity MAE: {res['test_mae_safe_capacity']} users | Time: {res['training_time_sec']}s")

    out_file = RESULTS_DIR / "batchnorm_experiments.json"
    out_file.write_text(json.dumps(results, indent=2) + "\n")
    print(f"\nSaved BatchNorm experiment report to: {out_file}")


if __name__ == "__main__":
    main()
