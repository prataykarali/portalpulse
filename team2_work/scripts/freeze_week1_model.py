"""Freeze the Week 1 XGBoost baseline. Does not retrain."""

from __future__ import annotations

import json
import pickle
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb
from xgboost import XGBRegressor

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "Module1_Data"
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
    "cpu_usage",
    "memory_usage",
    "network_usage",
    "latency_ms",
    "error_rate",
]
TARGET = "safe_capacity"
SLA_LATENCY = 800.0
SLA_ERROR = 0.01
SLA_CPU = 85.0


def metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    err = y_pred - y_true
    mae = float(np.mean(np.abs(err)))
    rmse = float(np.sqrt(np.mean(err**2)))
    ss_res = float(np.sum(err**2))
    ss_tot = float(np.sum((y_true - np.mean(y_true)) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot else float("nan")
    return {"MAE": mae, "RMSE": rmse, "R2": r2}


def status(users: np.ndarray, capacity: np.ndarray, cpu: np.ndarray, latency: np.ndarray, err: np.ndarray) -> np.ndarray:
    util = users / np.maximum(capacity, 1.0)
    sla = (cpu >= SLA_CPU) | (latency >= SLA_LATENCY) | (err >= SLA_ERROR)
    out = np.full(len(users), "SAFE", dtype=object)
    out[util >= 0.70] = "AT_RISK"
    out[(util >= 0.90) | sla] = "OVERLOADED"
    return out


def predict(model: xgb.Booster, frame: pd.DataFrame) -> np.ndarray:
    dmat = xgb.DMatrix(frame[FEATURES], feature_names=FEATURES)
    return np.asarray(model.predict(dmat), dtype=float)


def main() -> None:
    booster_path = MODEL_DIR / "xgboost_safe_capacity.json"
    meta_path = MODEL_DIR / "xgboost_metadata.json"
    test_path = DATA / "test.csv"
    val_path = DATA / "validation.csv"
    if not booster_path.exists():
        raise SystemExit(f"missing {booster_path}")
    if not test_path.exists():
        raise SystemExit("run team1_work/scripts/freeze_week1_data.py first")

    official = json.loads(meta_path.read_text())
    booster = xgb.Booster()
    booster.load_model(str(booster_path))

    regressor = XGBRegressor()
    regressor.load_model(str(booster_path))
    TEAM2_MODELS.mkdir(parents=True, exist_ok=True)
    TEAM2_RESULTS.mkdir(parents=True, exist_ok=True)
    pkl_path = TEAM2_MODELS / "xgboost_model.pkl"
    with pkl_path.open("wb") as f:
        pickle.dump(regressor, f)
    (MODEL_DIR / "xgboost_model.pkl").write_bytes(pkl_path.read_bytes())

    test = pd.read_csv(test_path, parse_dates=["timestamp"])
    val = pd.read_csv(val_path, parse_dates=["timestamp"])
    test_pred = predict(booster, test)
    val_pred = predict(booster, val)

    pred = test.copy()
    pred["predicted_safe_capacity"] = test_pred
    pred["residual"] = pred["predicted_safe_capacity"] - pred[TARGET]
    pred["utilization"] = pred["concurrent_users"] / pred["predicted_safe_capacity"].clip(lower=1.0)
    pred["predicted_status"] = status(
        pred["concurrent_users"].to_numpy(dtype=float),
        pred["predicted_safe_capacity"].to_numpy(dtype=float),
        pred["cpu_usage"].to_numpy(dtype=float),
        pred["latency_ms"].to_numpy(dtype=float),
        pred["error_rate"].to_numpy(dtype=float),
    )
    pred_path = TEAM2_RESULTS / "prediction_test.csv"
    pred.to_csv(pred_path, index=False)
    (MODEL_DIR / "prediction_test.csv").write_bytes(pred_path.read_bytes())

    gain = booster.get_score(importance_type="gain")
    total = sum(gain.values()) or 1.0
    importance = [
        {
            "feature": name,
            "gain": float(gain.get(name, 0.0)),
            "share_pct": 100.0 * float(gain.get(name, 0.0)) / total,
        }
        for name in FEATURES
    ]
    importance.sort(key=lambda row: row["gain"], reverse=True)

    feature_list = {
        "features": FEATURES,
        "target": TARGET,
        "feature_count": len(FEATURES),
        "input_order_is_important": True,
    }
    (TEAM2_MODELS / "feature_list.json").write_text(json.dumps(feature_list, indent=2) + "\n")
    (MODEL_DIR / "feature_list.json").write_text(json.dumps(feature_list, indent=2) + "\n")

    payload = {
        "frozen": True,
        "week": "Module 1 / Week 1",
        "do_not_retrain": True,
        "model_type": "XGBoost regressor",
        "task": "Regression",
        "target": TARGET,
        "input_features": FEATURES,
        "artifacts": {
            "xgboost_model.pkl": "sklearn-compatible XGBRegressor wrapper of the frozen booster",
            "xgboost_safe_capacity.json": "native XGBoost booster used by the dashboard",
            "feature_list.json": "locked input order",
            "prediction_test.csv": "frozen model scored on the published time-split test set",
        },
        "hyperparameters": official.get("best_parameters", {}),
        "official_training_metrics": {
            "validation": official["validation_metrics"],
            "test": official["test_metrics"],
            "note": (
                "Recorded when this booster was trained. The original training-row "
                "split was not checked in with the model."
            ),
        },
        "frozen_time_split_evaluation": {
            "split": "Module1_Data time split (train < 2025-07-06, val 2025-07-06–07-08, test ≥ 2025-07-09)",
            "validation": metrics(val[TARGET].to_numpy(dtype=float), val_pred),
            "test": metrics(test[TARGET].to_numpy(dtype=float), test_pred),
            "test_rows": int(len(test)),
            "note": "Same frozen booster. Not a new training run.",
        },
        "feature_importance": importance,
        "status_rule": {
            "utilization": "current_users / predicted_safe_capacity",
            "SAFE": "utilization < 0.70 and no SLA breach",
            "AT_RISK": "0.70 ≤ utilization < 0.90 and no SLA breach",
            "OVERLOADED": "utilization ≥ 0.90 or CPU≥85% or latency≥800ms or error_rate≥1%",
        },
        "caveats": [
            "Prototype estimate based on the trained model.",
            "R² on this historical dataset does not prove the model will work on a real IEM result day.",
            "This is not connected to the live IEM portal.",
            "Do not keep retraining randomly. This is the Week 1 baseline.",
        ],
    }
    metrics_path = TEAM2_RESULTS / "model_metrics.json"
    metrics_path.write_text(json.dumps(payload, indent=2) + "\n")
    (MODEL_DIR / "model_metrics.json").write_text(json.dumps(payload, indent=2) + "\n")
    print(json.dumps(payload["frozen_time_split_evaluation"], indent=2))


if __name__ == "__main__":
    main()
