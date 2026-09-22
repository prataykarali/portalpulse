"""Training and evaluation pipeline for PortalPulse Module 4 Action Intelligence.

Trains the PyTorch ActionPolicyMLP on synthetic state-action telemetry,
evaluates on test split, benchmarks single-sample inference latency,
and serializes artifacts for production serving.
"""

from __future__ import annotations

import json
import pickle
import time
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np
import torch
import torch.nn as nn
from sklearn.metrics import f1_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from torch.utils.data import DataLoader, TensorDataset

from backend.m4_action_intelligence.dataset_generator import generate_action_dataset
from backend.m4_action_intelligence.policy_net import (
    ActionPolicyMLP,
    get_device,
)
from backend.m4_action_intelligence.schema import (
    ACTION_INDEX_MAP,
    STATE_FEATURE_NAMES,
)

MODELS_DIR = Path(__file__).resolve().parent / "models"


def train_action_policy(
    n_samples: int = 25000,
    epochs: int = 20,
    batch_size: int = 64,
    learning_rate: float = 0.001,
    weight_decay: float = 1e-4,
    output_dir: Optional[Path] = None,
    random_state: int = 42,
) -> Dict[str, Any]:
    """Train, evaluate, benchmark, and serialize the deep action policy network.

    Args:
        n_samples: Number of synthetic training samples.
        epochs: Training iterations.
        batch_size: Mini-batch size.
        learning_rate: Initial AdamW learning rate.
        weight_decay: L2 regularization penalty.
        output_dir: Target directory for artifacts.
        random_state: RNG seed.

    Returns:
        Dictionary of training metadata, metrics, and artifact locations.
    """
    target_dir = output_dir or MODELS_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    device = get_device()

    print("=" * 72)
    print(f"PortalPulse Week 4: Training Module 4 Action Intelligence (Device: {device})")
    print("=" * 72)

    # 1. Dataset Generation
    print(f"\n[Step 1/5] Synthesizing {n_samples} state-action samples across 11 SRE actions...")
    X, y, _ = generate_action_dataset(n_samples=n_samples, random_state=random_state)
    print(f"Synthesized feature shape: {X.shape}, label shape: {y.shape}")

    # 2. Stratified Splits (80% train, 10% val, 10% test)
    print("\n[Step 2/5] Creating stratified 80/10/10 train/val/test splits...")
    X_train_val, X_test, y_train_val, y_test = train_test_split(
        X, y, test_size=0.10, random_state=random_state, stratify=y
    )
    X_train, X_val, y_train, y_val = train_test_split(
        X_train_val, y_train_val, test_size=0.1111, random_state=random_state, stratify=y_train_val
    )

    # Standardize input features
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train).astype(np.float32)
    X_val_scaled = scaler.transform(X_val).astype(np.float32)
    X_test_scaled = scaler.transform(X_test).astype(np.float32)

    # Save scaler
    scaler_path = target_dir / "scaler.pkl"
    with open(scaler_path, "wb") as f:
        pickle.dump(scaler, f)
    print(f"Saved fitted StandardScaler to {scaler_path}")

    # Convert to PyTorch DataLoaders
    train_dataset = TensorDataset(torch.from_numpy(X_train_scaled), torch.from_numpy(y_train))
    val_dataset = TensorDataset(torch.from_numpy(X_val_scaled), torch.from_numpy(y_val))
    _test_dataset = TensorDataset(torch.from_numpy(X_test_scaled), torch.from_numpy(y_test))

    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False)

    # 3. Model Initialization
    print(f"\n[Step 3/5] Instantiating Deep ActionPolicyMLP on {device}...")
    model = ActionPolicyMLP(input_dim=13, output_dim=11).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate, weight_decay=weight_decay)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)
    criterion = nn.CrossEntropyLoss()

    total_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"Model parameter count: {total_params:,}")

    # 4. Training Loop
    print(f"\n[Step 4/5] Training for {epochs} epochs...")
    best_val_loss = float("inf")
    best_state: Optional[Dict[str, Any]] = None

    for epoch in range(1, epochs + 1):
        model.train()
        train_loss = 0.0
        train_correct = 0
        total_train = 0

        for batch_x, batch_y in train_loader:
            batch_x = batch_x.to(device)
            batch_y = batch_y.to(device)

            optimizer.zero_grad()
            logits = model(batch_x)
            loss = criterion(logits, batch_y)
            loss.backward()
            optimizer.step()

            train_loss += loss.item() * len(batch_y)
            preds = torch.argmax(logits, dim=-1)
            train_correct += (preds == batch_y).sum().item()
            total_train += len(batch_y)

        scheduler.step()

        # Validation
        model.eval()
        val_loss = 0.0
        val_correct = 0
        total_val = 0

        with torch.no_grad():
            for batch_x, batch_y in val_loader:
                batch_x = batch_x.to(device)
                batch_y = batch_y.to(device)
                logits = model(batch_x)
                loss = criterion(logits, batch_y)

                val_loss += loss.item() * len(batch_y)
                preds = torch.argmax(logits, dim=-1)
                val_correct += (preds == batch_y).sum().item()
                total_val += len(batch_y)

        epoch_train_loss = train_loss / total_train
        epoch_train_acc = train_correct / total_train
        epoch_val_loss = val_loss / total_val
        epoch_val_acc = val_correct / total_val

        if epoch_val_loss < best_val_loss:
            best_val_loss = epoch_val_loss
            best_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}

        if epoch % 5 == 0 or epoch == epochs:
            print(
                f"Epoch {epoch:2d}/{epochs} | "
                f"Train Loss: {epoch_train_loss:.4f}, Acc: {epoch_train_acc:.4f} | "
                f"Val Loss: {epoch_val_loss:.4f}, Acc: {epoch_val_acc:.4f}"
            )

    # Load best weights
    if best_state is not None:
        model.load_state_dict(best_state)
    model.eval()

    # 5. Untouched Test Set Evaluation
    print("\n[Step 5/5] Evaluating on untouched test set...")
    with torch.no_grad():
        test_x_tensor = torch.from_numpy(X_test_scaled).to(device)
        test_logits = model(test_x_tensor)
        test_preds = torch.argmax(test_logits, dim=-1).cpu().numpy()

    test_acc = float(np.mean(test_preds == y_test))
    macro_f1 = float(f1_score(y_test, test_preds, average="macro"))
    print(f"Test Accuracy: {test_acc:.4f} (Requirement >= 0.88)")
    print(f"Macro F1-Score: {macro_f1:.4f} (Requirement >= 0.85)")

    # Benchmark Single-Sample Inference Latency (1,000 iterations)
    print("\nBenchmarking single-sample forward pass latency (1,000 runs)...")
    single_sample = torch.from_numpy(X_test_scaled[0:1]).to(device)
    latencies = []
    for _ in range(1000):
        t0 = time.perf_counter()
        _ = model.predict_proba(single_sample)
        latencies.append((time.perf_counter() - t0) * 1000.0)

    p50_latency = float(np.percentile(latencies, 50))
    p95_latency = float(np.percentile(latencies, 95))
    p99_latency = float(np.percentile(latencies, 99))
    print(f"Inference Latency: p50={p50_latency:.3f}ms | p95={p95_latency:.3f}ms | p99={p99_latency:.3f}ms")

    # Serialize PyTorch Checkpoint
    checkpoint_path = target_dir / "action_mlp_policy.pt"
    metadata = {
        "model_architecture": "ActionPolicyMLP",
        "input_dim": 13,
        "output_dim": 11,
        "device": str(device),
        "parameter_count": total_params,
        "test_accuracy": round(test_acc, 4),
        "macro_f1": round(macro_f1, 4),
        "latency_ms": {
            "p50": round(p50_latency, 3),
            "p95": round(p95_latency, 3),
            "p99": round(p99_latency, 3),
        },
        "features": STATE_FEATURE_NAMES,
        "actions": [a.value for a in ACTION_INDEX_MAP.values()],
    }
    model.save_checkpoint(checkpoint_path, extra_metadata=metadata)
    print(f"Saved PyTorch policy model to {checkpoint_path}")

    # Save JSON metadata
    metadata_path = target_dir / "action_metadata.json"
    metadata_path.write_text(json.dumps(metadata, indent=2))
    print(f"Saved Action Intelligence metadata to {metadata_path}")

    return metadata


if __name__ == "__main__":
    train_action_policy()
