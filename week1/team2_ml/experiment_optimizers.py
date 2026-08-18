"""Week 1 Experiment: Optimizers (Adam vs SGD with Momentum)."""

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
from week1.team2_ml.model import PortalPulseMLP

RESULTS_DIR = ROOT / "week1" / "team2_ml" / "results"


def train_and_eval(optimizer_name: str, epochs: int = 25, lr: float = 0.005) -> dict:
    train_loader, val_loader, test_loader, scaler = load_dataloaders(batch_size=128)
    model = PortalPulseMLP(in_features=6, hidden_dims=(64, 32), out_features=3, activation="relu")
    criterion = nn.MSELoss()

    if optimizer_name.lower() == "adam":
        optimizer = optim.Adam(model.parameters(), lr=lr)
    elif optimizer_name.lower() == "sgd":
        optimizer = optim.SGD(model.parameters(), lr=lr, momentum=0.9)
    else:
        raise ValueError(f"Unknown optimizer: {optimizer_name}")

    train_losses = []
    val_losses = []

    t0 = time.perf_counter()
    for epoch in range(epochs):
        model.train()
        running_train = 0.0
        for X_b, y_b in train_loader:
            optimizer.zero_grad()
            preds = model.forward(X_b)
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
                v_preds = model.forward(X_v)
                v_loss = criterion(v_preds, y_v)
                running_val += v_loss.item() * len(X_v)

        val_loss = running_val / len(val_loader.dataset)
        val_losses.append(round(val_loss, 4))

    elapsed = round(time.perf_counter() - t0, 2)

    # Evaluate unscaled MAE on test set
    model.eval()
    all_preds = []
    all_targets = []
    with torch.no_grad():
        for X_t, y_t in test_loader:
            all_preds.append(model.forward(X_t).numpy())
            all_targets.append(y_t.numpy())

    preds_scaled = np.vstack(all_preds)
    targets_scaled = np.vstack(all_targets)

    preds_raw = scaler.inverse_transform_y(preds_scaled)
    targets_raw = scaler.inverse_transform_y(targets_scaled)

    mae_per_target = np.mean(np.abs(preds_raw - targets_raw), axis=0)

    return {
        "optimizer": optimizer_name.upper(),
        "final_train_loss_mse": train_losses[-1],
        "final_val_loss_mse": val_losses[-1],
        "test_mae_cpu_pct": round(float(mae_per_target[0]), 2),
        "test_mae_latency_ms": round(float(mae_per_target[1]), 2),
        "test_mae_safe_capacity": round(float(mae_per_target[2]), 2),
        "training_time_sec": elapsed,
        "train_loss_history": train_losses,
        "val_loss_history": val_losses,
    }


def main() -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    optimizers = ["Adam", "SGD"]
    results = []

    print("Running Week 1 Optimizer Experiments (Adam vs SGD with Momentum)...")
    for opt in optimizers:
        res = train_and_eval(opt)
        results.append(res)
        print(f"[{res['optimizer']}] Final Val MSE: {res['final_val_loss_mse']} | Safe Capacity MAE: {res['test_mae_safe_capacity']} users | Time: {res['training_time_sec']}s")

    out_file = RESULTS_DIR / "optimizer_experiments.json"
    out_file.write_text(json.dumps(results, indent=2) + "\n")
    print(f"\nSaved optimizer experiment report to: {out_file}")


if __name__ == "__main__":
    main()
