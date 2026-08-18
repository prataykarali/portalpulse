"""Week 1 Dataset and DataLoader module for PyTorch MLP training."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Tuple

import numpy as np
import pandas as pd
import torch
from torch.utils.data import Dataset, DataLoader

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "Module1_Data"

INPUT_FEATURES = [
    "hour",
    "day_of_week",
    "is_weekend",
    "is_result_window",
    "concurrent_users",
    "requests_per_sec",
]

TARGET_FEATURES = [
    "cpu_usage",
    "latency_ms",
    "safe_capacity",
]


class TrafficDataset(Dataset):
    """PyTorch Dataset for PortalPulse system telemetry."""

    def __init__(self, X: np.ndarray, y: np.ndarray) -> None:
        self.X = torch.tensor(X, dtype=torch.float32)
        self.y = torch.tensor(y, dtype=torch.float32)

    def __len__(self) -> int:
        return len(self.X)

    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor]:
        return self.X[idx], self.y[idx]


class Standardizer:
    """Mean-variance standardizer fitted on training data only."""

    def __init__(self) -> None:
        self.mean_x: np.ndarray | None = None
        self.std_x: np.ndarray | None = None
        self.mean_y: np.ndarray | None = None
        self.std_y: np.ndarray | None = None

    def fit(self, X: np.ndarray, y: np.ndarray) -> "Standardizer":
        self.mean_x = np.mean(X, axis=0)
        self.std_x = np.std(X, axis=0) + 1e-7
        self.mean_y = np.mean(y, axis=0)
        self.std_y = np.std(y, axis=0) + 1e-7
        return self

    def transform_x(self, X: np.ndarray) -> np.ndarray:
        return (X - self.mean_x) / self.std_x

    def transform_y(self, y: np.ndarray) -> np.ndarray:
        return (y - self.mean_y) / self.std_y

    def inverse_transform_y(self, y_scaled: np.ndarray) -> np.ndarray:
        return y_scaled * self.std_y + self.mean_y

    def to_dict(self) -> dict:
        return {
            "mean_x": self.mean_x.tolist(),
            "std_x": self.std_x.tolist(),
            "mean_y": self.mean_y.tolist(),
            "std_y": self.std_y.tolist(),
            "input_features": INPUT_FEATURES,
            "target_features": TARGET_FEATURES,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Standardizer":
        s = cls()
        s.mean_x = np.array(data["mean_x"], dtype=np.float32)
        s.std_x = np.array(data["std_x"], dtype=np.float32)
        s.mean_y = np.array(data["mean_y"], dtype=np.float32)
        s.std_y = np.array(data["std_y"], dtype=np.float32)
        return s


def load_dataloaders(
    batch_size: int = 128,
) -> Tuple[DataLoader, DataLoader, DataLoader, Standardizer]:
    """Load train, val, and test DataLoaders with strict no-leakage standardization."""
    train_df = pd.read_csv(DATA_DIR / "train.csv")
    val_df = pd.read_csv(DATA_DIR / "validation.csv")
    test_df = pd.read_csv(DATA_DIR / "test.csv")

    X_train_raw = train_df[INPUT_FEATURES].to_numpy(dtype=np.float32)
    y_train_raw = train_df[TARGET_FEATURES].to_numpy(dtype=np.float32)

    X_val_raw = val_df[INPUT_FEATURES].to_numpy(dtype=np.float32)
    y_val_raw = val_df[TARGET_FEATURES].to_numpy(dtype=np.float32)

    X_test_raw = test_df[INPUT_FEATURES].to_numpy(dtype=np.float32)
    y_test_raw = test_df[TARGET_FEATURES].to_numpy(dtype=np.float32)

    scaler = Standardizer().fit(X_train_raw, y_train_raw)

    train_ds = TrafficDataset(scaler.transform_x(X_train_raw), scaler.transform_y(y_train_raw))
    val_ds = TrafficDataset(scaler.transform_x(X_val_raw), scaler.transform_y(y_val_raw))
    test_ds = TrafficDataset(scaler.transform_x(X_test_raw), scaler.transform_y(y_test_raw))

    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False)
    test_loader = DataLoader(test_ds, batch_size=batch_size, shuffle=False)

    return train_loader, val_loader, test_loader, scaler
