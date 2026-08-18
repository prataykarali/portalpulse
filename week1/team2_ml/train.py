"""Week 1 PyTorch MLP training script with checkpointing and metrics export."""

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

MODELS_DIR = ROOT / "week1" / "team2_ml" / "models"
RESULTS_DIR = ROOT / "week1" / "team2_ml" / "results"


def main(epochs: int = 35, lr: float = 0.005, batch_size: int = 128) -> None:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    train_loader, val_loader, test_loader, scaler = load_dataloaders(batch_size=batch_size)

    # Initialize PyTorch MLP model
    model = PortalPulseMLP(in_features=6, hidden_dims=(64, 32), out_features=3, activation="relu")
    criterion = nn.MSELoss()
    optimizer = optim.Adam(model.parameters(), lr=lr)

    history = {"train_loss": [], "val_loss": []}
    print(f"Training Week 1 PyTorch MLP for {epochs} epochs...")

    t0 = time.perf_counter()
    best_val_loss = float("inf")
    best_model_state = None

    for epoch in range(1, epochs + 1):
        model.train()
        train_loss_accum = 0.0
        for X_batch, y_batch in train_loader:
            optimizer.zero_grad()
            outputs = model(X_batch)
            loss = criterion(outputs, y_batch)
            loss.backward()
            optimizer.step()
            train_loss_accum += loss.item() * len(X_batch)

        epoch_train_loss = train_loss_accum / len(train_loader.dataset)
        history["train_loss"].append(round(epoch_train_loss, 5))

        model.eval()
        val_loss_accum = 0.0
        with torch.no_grad():
            for X_val, y_val in val_loader:
                v_out = model(X_val)
                v_loss = criterion(v_out, y_val)
                val_loss_accum += v_loss.item() * len(X_val)

        epoch_val_loss = val_loss_accum / len(val_loader.dataset)
        history["val_loss"].append(round(epoch_val_loss, 5))

        if epoch_val_loss < best_val_loss:
            best_val_loss = epoch_val_loss
            best_model_state = model.state_dict()

        if epoch % 5 == 0 or epoch == epochs:
            print(f"Epoch {epoch:02d}/{epochs:02d} | Train MSE: {epoch_train_loss:.5f} | Val MSE: {epoch_val_loss:.5f}")

    train_duration = round(time.perf_counter() - t0, 2)

    # Restore best weights and evaluate on test split
    model.load_state_dict(best_model_state)
    model.eval()

    all_preds = []
    all_targets = []
    with torch.no_grad():
        for X_test, y_test in test_loader:
            all_preds.append(model(X_test).numpy())
            all_targets.append(y_test.numpy())

    preds_scaled = np.vstack(all_preds)
    targets_scaled = np.vstack(all_targets)

    preds_raw = scaler.inverse_transform_y(preds_scaled)
    targets_raw = scaler.inverse_transform_y(targets_scaled)

    # Calculate MAE, RMSE, and R2 per target
    target_names = ["cpu_usage", "latency_ms", "safe_capacity"]
    test_metrics = {}
    for i, name in enumerate(target_names):
        y_t = targets_raw[:, i]
        y_p = preds_raw[:, i]
        mae = float(np.mean(np.abs(y_p - y_t)))
        rmse = float(np.sqrt(np.mean((y_p - y_t) ** 2)))
        ss_res = float(np.sum((y_t - y_p) ** 2))
        ss_tot = float(np.sum((y_t - np.mean(y_t)) ** 2))
        r2 = 1.0 - (ss_res / ss_tot) if ss_tot > 0 else float("nan")
        test_metrics[name] = {"MAE": round(mae, 2), "RMSE": round(rmse, 2), "R2": round(r2, 4)}

    print("\nWeek 1 Test Split Metrics:")
    print(json.dumps(test_metrics, indent=2))

    # Save model weights & metadata
    torch.save(best_model_state, MODELS_DIR / "pytorch_mlp_week1.pth")
    scaler_payload = scaler.to_dict()
    (MODELS_DIR / "standardizer_week1.json").write_text(json.dumps(scaler_payload, indent=2) + "\n")

    summary_payload = {
        "model_type": "PyTorch Multi-Layer Perceptron (MLP)",
        "framework": "PyTorch",
        "week": "Module 1 / Week 1",
        "architecture": {
            "in_features": 6,
            "hidden_layers": [64, 32],
            "out_features": 3,
            "activation": "ReLU",
            "optimizer": "Adam (lr=0.005)",
        },
        "training_time_sec": train_duration,
        "epochs": epochs,
        "best_val_loss_mse": round(best_val_loss, 5),
        "test_metrics": test_metrics,
        "history": history,
    }
    (RESULTS_DIR / "week1_training_summary.json").write_text(json.dumps(summary_payload, indent=2) + "\n")
    print(f"\nWeek 1 artifacts successfully saved to {MODELS_DIR} and {RESULTS_DIR}!")


if __name__ == "__main__":
    main()
