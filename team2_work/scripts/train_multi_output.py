"""Multi-output regression training pipeline for PortalPulse.

Trains a model to predict multiple system response targets simultaneously:
1. safe_capacity (SLA-preserving max concurrent active users)
2. latency_ms (Expected response time under load)
3. cpu_usage (Expected CPU utilization)
"""

from __future__ import annotations

import json
import pickle
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.multioutput import MultiOutputRegressor
import xgboost as xgb
from xgboost import XGBRegressor

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "Module1_Data"
MODEL_DIR = ROOT / "traffic_bot_model"
TEAM2_MODELS = ROOT / "team2_work" / "models"
TEAM2_RESULTS = ROOT / "team2_work" / "results"

FEATURES = [
    "hour",
    "day_of_week",
    "is_weekend",
    "is_result_window",
    "concurrent_users",
    "requests_per_sec",
    "memory_usage",
    "network_usage",
]

TARGETS = [
    "safe_capacity",
    "latency_ms",
    "cpu_usage",
]

SLA_LATENCY = 800.0
SLA_ERROR = 0.01
SLA_CPU = 85.0


def compute_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    res = {}
    for i, col in enumerate(TARGETS):
        yt = y_true[:, i]
        yp = y_pred[:, i]
        err = yp - yt
        mae = float(np.mean(np.abs(err)))
        rmse = float(np.sqrt(np.mean(err**2)))
        ss_res = float(np.sum(err**2))
        ss_tot = float(np.sum((yt - np.mean(yt)) ** 2))
        r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")
        res[col] = {"MAE": round(mae, 3), "RMSE": round(rmse, 3), "R2": round(r2, 4)}
    return res


def main() -> None:
    train_path = DATA_DIR / "train.csv"
    val_path = DATA_DIR / "validation.csv"
    test_path = DATA_DIR / "test.csv"

    if not train_path.exists():
        raise SystemExit(f"Missing training data at {train_path}")

    train_df = pd.read_csv(train_path)
    val_df = pd.read_csv(val_path)
    test_df = pd.read_csv(test_path)

    X_train = train_df[FEATURES].to_numpy(dtype=float)
    y_train = train_df[TARGETS].to_numpy(dtype=float)

    X_val = val_df[FEATURES].to_numpy(dtype=float)
    y_val = val_df[TARGETS].to_numpy(dtype=float)

    X_test = test_df[FEATURES].to_numpy(dtype=float)
    y_test = test_df[TARGETS].to_numpy(dtype=float)

    print(f"Training MultiOutputRegressor on {len(train_df)} records...")
    base_estimator = XGBRegressor(
        n_estimators=120,
        max_depth=5,
        learning_rate=0.08,
        subsample=0.85,
        colsample_bytree=0.85,
        random_state=42,
        n_jobs=-1,
    )
    model = MultiOutputRegressor(base_estimator)
    model.fit(X_train, y_train)

    train_preds = model.predict(X_train)
    val_preds = model.predict(X_val)
    test_preds = model.predict(X_test)

    train_eval = compute_metrics(y_train, train_preds)
    val_eval = compute_metrics(y_val, val_preds)
    test_eval = compute_metrics(y_test, test_preds)

    print("Test Evaluation:")
    print(json.dumps(test_eval, indent=2))

    TEAM2_MODELS.mkdir(parents=True, exist_ok=True)
    TEAM2_RESULTS.mkdir(parents=True, exist_ok=True)
    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    pkl_path = TEAM2_MODELS / "multi_output_model.pkl"
    with pkl_path.open("wb") as f:
        pickle.dump(model, f)
    (MODEL_DIR / "multi_output_model.pkl").write_bytes(pkl_path.read_bytes())

    metadata = {
        "model_type": "MultiOutputRegressor(XGBRegressor)",
        "task": "Multi-Target System State & Capacity Prediction",
        "input_features": FEATURES,
        "target_variables": TARGETS,
        "train_samples": int(len(train_df)),
        "val_samples": int(len(val_df)),
        "test_samples": int(len(test_df)),
        "metrics": {
            "train": train_eval,
            "validation": val_eval,
            "test": test_eval,
        },
        "sla_definitions": {
            "p95_latency_ms": SLA_LATENCY,
            "error_rate_max": SLA_ERROR,
            "cpu_usage_pct": SLA_CPU,
        },
    }

    meta_path = TEAM2_RESULTS / "multi_output_metadata.json"
    meta_path.write_text(json.dumps(metadata, indent=2) + "\n")
    (MODEL_DIR / "multi_output_metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")

    print("Multi-output model and metadata successfully saved!")


if __name__ == "__main__":
    main()
