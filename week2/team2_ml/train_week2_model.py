"""Week 2 Final Multi-Output PyTorch Model Training & Verification Pipeline.

Trains the shared multi-output neural network with BatchNorm1d, Dropout(0.15), and He Normal Init.
Produces complete ground-truth vs predicted validation metrics on the untouched test split.
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

MODELS_DIR = ROOT / "week2" / "team2_ml" / "models"
RESULTS_DIR = ROOT / "week2" / "team2_ml" / "results"


def main(epochs: int = 40, lr: float = 0.004, batch_size: int = 128) -> None:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    train_loader, val_loader, test_loader, scaler = load_dataloaders(batch_size=batch_size)

    # Initialize optimized Week 2 Multi-Output Model
    model = AdvancedMultiOutputMLP(
        in_features=6,
        hidden_dims=(128, 64, 32),
        out_features=3,
        use_batchnorm=True,
        dropout_p=0.15,
        init_type="he",
    )
    criterion = nn.MSELoss()
    optimizer = optim.Adam(model.parameters(), lr=lr, weight_decay=1e-4)

    history = {"train_loss": [], "val_loss": []}
    print(f"Training Week 2 Optimized Multi-Output PyTorch Model for {epochs} epochs...")

    t0 = time.perf_counter()
    best_val_loss = float("inf")
    best_state = None

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
            best_state = model.state_dict()

        if epoch % 5 == 0 or epoch == epochs:
            print(f"Epoch {epoch:02d}/{epochs:02d} | Train MSE: {epoch_train_loss:.5f} | Val MSE: {epoch_val_loss:.5f}")

    train_duration = round(time.perf_counter() - t0, 2)

    # Evaluate best state on test set
    model.load_state_dict(best_state)
    model.eval()

    all_preds, all_targets = [], []
    with torch.no_grad():
        for X_test, y_test in test_loader:
            all_preds.append(model(X_test).numpy())
            all_targets.append(y_test.numpy())

    preds_scaled = np.vstack(all_preds)
    targets_scaled = np.vstack(all_targets)
    preds_raw = scaler.inverse_transform_y(preds_scaled)
    targets_raw = scaler.inverse_transform_y(targets_scaled)

    target_names = ["cpu_usage", "latency_ms", "safe_capacity"]
    test_metrics = {}
    sample_evaluations = []

    for i, name in enumerate(target_names):
        y_t = targets_raw[:, i]
        y_p = preds_raw[:, i]
        mae = float(np.mean(np.abs(y_p - y_t)))
        rmse = float(np.sqrt(np.mean((y_p - y_t) ** 2)))
        ss_res = float(np.sum((y_t - y_p) ** 2))
        ss_tot = float(np.sum((y_t - np.mean(y_t)) ** 2))
        r2 = 1.0 - (ss_res / ss_tot) if ss_tot > 0 else float("nan")
        test_metrics[name] = {"MAE": round(mae, 2), "RMSE": round(rmse, 2), "R2": round(r2, 4)}

    # Collect sample actual vs predicted rows for validation transparency
    indices = [0, 50, 100, 250, 500, 1000, 2000, 4000]
    for idx in indices:
        if idx < len(targets_raw):
            sample_evaluations.append({
                "sample_index": idx,
                "actual_safe_capacity": round(float(targets_raw[idx, 2]), 1),
                "predicted_safe_capacity": round(float(preds_raw[idx, 2]), 1),
                "error_users": round(float(preds_raw[idx, 2] - targets_raw[idx, 2]), 1),
                "actual_latency_ms": round(float(targets_raw[idx, 1]), 1),
                "predicted_latency_ms": round(float(preds_raw[idx, 1]), 1),
                "actual_cpu_pct": round(float(targets_raw[idx, 0]), 1),
                "predicted_cpu_pct": round(float(preds_raw[idx, 0]), 1),
            })

    print("\nWeek 2 Final Test Split Metrics:")
    print(json.dumps(test_metrics, indent=2))

    # Save artifacts
    torch.save(best_state, MODELS_DIR / "pytorch_multi_output_week2.pth")
    scaler_payload = scaler.to_dict()
    (MODELS_DIR / "standardizer_week2.json").write_text(json.dumps(scaler_payload, indent=2) + "\n")

    summary_payload = {
        "model_type": "Optimized PyTorch Multi-Output MLP",
        "week": "Module 2 / Week 2",
        "techniques_applied": [
            "He Normal (Kaiming) Weight Initialization",
            "Batch Normalization (nn.BatchNorm1d)",
            "Dropout Regularization (p=0.15)",
            "L2 Weight Decay (1e-4)",
            "Shared Multi-Output Prediction Trunk",
        ],
        "training_time_sec": train_duration,
        "epochs": epochs,
        "best_val_loss_mse": round(best_val_loss, 5),
        "test_metrics": test_metrics,
        "sample_ground_truth_vs_predicted": sample_evaluations,
        "history": history,
    }
    (RESULTS_DIR / "week2_training_summary.json").write_text(json.dumps(summary_payload, indent=2) + "\n")
    (RESULTS_DIR / "final_mlp_validation.json").write_text(json.dumps(summary_payload, indent=2) + "\n")
    print(f"\nWeek 2 model and validation reports saved successfully to {MODELS_DIR} and {RESULTS_DIR}!")


if __name__ == "__main__":
    main()
