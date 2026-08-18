"""Train and benchmark 5 model architectures for safe capacity prediction.

Architectures evaluated:
1. Linear / Ridge Regression (Linear Baseline)
2. Random Forest Regressor (Bagged Ensemble)
3. XGBoost Regressor (Gradient Boosted Trees)
4. LightGBM / HistGradientBoosting (Fast Histogram GBDT)
5. Multi-Layer Perceptron / ANN (Neural Network)
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor, HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
import xgboost as xgb
from xgboost import XGBRegressor

try:
    import lightgbm as lgb
    from lightgbm import LGBMRegressor
    HAS_LIGHTGBM = True
except ImportError:
    HAS_LIGHTGBM = False

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "Module1_Data"
RESULTS_DIR = ROOT / "team2_work" / "results"
MODELS_DIR = ROOT / "team2_work" / "models"

FEATURES = [
    "hour",
    "day_of_week",
    "is_weekend",
    "is_result_window",
    "concurrent_users",
    "requests_per_sec",
    "cpu_usage",
    "memory_usage",
    "network_usage",
    "latency_ms",
    "error_rate",
]
TARGET = "safe_capacity"


def compute_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    err = y_pred - y_true
    mae = float(np.mean(np.abs(err)))
    rmse = float(np.sqrt(np.mean(err**2)))
    ss_res = float(np.sum(err**2))
    ss_tot = float(np.sum((y_true - np.mean(y_true)) ** 2))
    r2 = 1.0 - (ss_res / ss_tot) if ss_tot > 0 else float("nan")
    return {
        "MAE": round(mae, 2),
        "RMSE": round(rmse, 2),
        "R2": round(r2, 4),
    }


def get_models() -> dict:
    models = {
        "Linear / Ridge Regression": Pipeline([
            ("scaler", StandardScaler()),
            ("regressor", Ridge(alpha=1.0, random_state=42)),
        ]),
        "Random Forest": RandomForestRegressor(
            n_estimators=100,
            max_depth=12,
            min_samples_split=5,
            random_state=42,
            n_jobs=-1,
        ),
        "XGBoost": XGBRegressor(
            n_estimators=200,
            max_depth=6,
            learning_rate=0.08,
            subsample=0.85,
            colsample_bytree=0.85,
            random_state=42,
            n_jobs=-1,
        ),
        "LightGBM": (
            LGBMRegressor(
                n_estimators=200,
                max_depth=6,
                learning_rate=0.08,
                subsample=0.85,
                colsample_bytree=0.85,
                random_state=42,
                n_jobs=-1,
                verbose=-1,
            )
            if HAS_LIGHTGBM
            else HistGradientBoostingRegressor(
                max_iter=200,
                max_depth=6,
                learning_rate=0.08,
                random_state=42,
            )
        ),
        "MLP / ANN": Pipeline([
            ("scaler", StandardScaler()),
            (
                "regressor",
                MLPRegressor(
                    hidden_layer_sizes=(64, 32),
                    activation="relu",
                    solver="adam",
                    alpha=0.001,
                    max_iter=150,
                    random_state=42,
                    early_stopping=True,
                ),
            ),
        ]),
    }
    return models


def main() -> None:
    train_df = pd.read_csv(DATA_DIR / "train.csv")
    val_df = pd.read_csv(DATA_DIR / "validation.csv")
    test_df = pd.read_csv(DATA_DIR / "test.csv")

    X_train = train_df[FEATURES]
    y_train = train_df[TARGET].to_numpy(dtype=float)

    X_val = val_df[FEATURES]
    y_val = val_df[TARGET].to_numpy(dtype=float)

    X_test = test_df[FEATURES]
    y_test = test_df[TARGET].to_numpy(dtype=float)

    models = get_models()
    comparison_results = []

    print(f"Training and benchmarking {len(models)} models on {len(X_train)} training records...\n")

    for name, model in models.items():
        t0 = time.perf_counter()
        model.fit(X_train, y_train)
        train_time_sec = round(time.perf_counter() - t0, 3)

        # Measure inference latency on test set
        t1 = time.perf_counter()
        test_preds = model.predict(X_test)
        inference_time_ms = round((time.perf_counter() - t1) * 1000 / len(X_test), 4)

        train_preds = model.predict(X_train)
        val_preds = model.predict(X_val)

        train_m = compute_metrics(y_train, train_preds)
        val_m = compute_metrics(y_val, val_preds)
        test_m = compute_metrics(y_test, test_preds)

        row = {
            "model_name": name,
            "train_mae": train_m["MAE"],
            "val_mae": val_m["MAE"],
            "test_mae": test_m["MAE"],
            "test_rmse": test_m["RMSE"],
            "test_r2": test_m["R2"],
            "train_time_sec": train_time_sec,
            "inference_ms_per_sample": inference_time_ms,
        }
        comparison_results.append(row)
        print(f"[{name}] Test MAE: {test_m['MAE']} users | Test R2: {test_m['R2']} | Train Time: {train_time_sec}s")

    comparison_df = pd.DataFrame(comparison_results).sort_values("test_mae", ascending=True)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    json_path = RESULTS_DIR / "model_comparison.json"
    csv_path = RESULTS_DIR / "model_comparison.csv"
    (ROOT / "traffic_bot_model" / "model_comparison.json").write_text(
        json.dumps(comparison_results, indent=2) + "\n"
    )

    comparison_df.to_json(json_path, orient="records", indent=2)
    comparison_df.to_csv(csv_path, index=False)

    print("\nBenchmark Summary:")
    print(comparison_df.to_string(index=False))


if __name__ == "__main__":
    main()
