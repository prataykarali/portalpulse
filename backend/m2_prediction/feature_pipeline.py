"""PortalPulse Module 2: Feature Engineering & Dataset Pipeline.

Loads historical telemetry data, computes 9 lag/rolling features without future data leakage,
constructs multi-horizon targets (+5m, +10m, +15m, safe_capacity), and maps live M1 telemetry
into model inference tensors.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple, Union

import numpy as np
import pandas as pd

from backend.m1_monitoring.schema import DerivedFeatures, RawTelemetry

# Feature column contract (ordered feature matrix for M2 models)
BASE_FEATURE_COLUMNS: List[str] = [
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

LAG_ROLLING_COLUMNS: List[str] = [
    "cpu_lag_1",
    "cpu_lag_5",
    "rps_lag_1",
    "rps_lag_5",
    "rolling_rps_5m",
    "rolling_latency_5m",
    "rolling_cpu_5m",
    "traffic_growth_rate",
    "error_growth_rate",
]

FEATURE_COLUMNS: List[str] = BASE_FEATURE_COLUMNS + LAG_ROLLING_COLUMNS

TARGET_COLUMNS: List[str] = [
    "cpu_5m",
    "cpu_10m",
    "cpu_15m",
    "latency_5m",
    "latency_10m",
    "latency_15m",
    "rps_5m",
    "rps_10m",
    "rps_15m",
    "safe_capacity",
]

# Known result window dates in Module 1 dataset
RESULT_WINDOW_DATES = {"2025-06-20", "2025-06-21", "2025-06-28"}

# Standard SLA operational limits
SLA_LATENCY_MS: float = 800.0
SLA_CPU_PERCENT: float = 85.0
SLA_ERROR_RATE: float = 0.01


def compute_lag_and_rolling_features(df: pd.DataFrame) -> pd.DataFrame:
    """Compute the 9 lag, rolling, and momentum features along the temporal axis.

    Features strictly utilize observations at or before time t to prevent data leakage:
    - cpu_lag_1: CPU utilization at t-1 (1 minute ago)
    - cpu_lag_5: CPU utilization at t-5 (5 minutes ago)
    - rps_lag_1: RPS at t-1
    - rps_lag_5: RPS at t-5
    - rolling_rps_5m: Rolling 5-minute mean RPS [t-4..t]
    - rolling_latency_5m: Rolling 5-minute mean latency [t-4..t]
    - rolling_cpu_5m: Rolling 5-minute mean CPU [t-4..t]
    - traffic_growth_rate: Velocity (RPS_t - RPS_lag5) / max(RPS_lag5, 1.0)
    - error_growth_rate: Velocity (error_t - error_lag5) / max(error_lag5, 0.001)

    Args:
        df: Telemetry DataFrame containing base columns.

    Returns:
        DataFrame with the 9 lag and rolling columns appended, with boundary NaNs backfilled.
    """
    out = df.copy()

    # Normalize column names if raw schema is supplied
    col_map = {
        "cpu_percent": "cpu_usage",
        "response_time": "latency_ms",
        "active_users": "concurrent_users",
        "ram_percent": "memory_usage",
        "network_out": "network_usage",
    }
    for old_col, new_col in col_map.items():
        if old_col in out.columns and new_col not in out.columns:
            out[new_col] = out[old_col]

    # Temporal Lags (t-1 and t-5)
    out["cpu_lag_1"] = out["cpu_usage"].shift(1).bfill()
    out["cpu_lag_5"] = out["cpu_usage"].shift(5).bfill()
    out["rps_lag_1"] = out["requests_per_sec"].shift(1).bfill()
    out["rps_lag_5"] = out["requests_per_sec"].shift(5).bfill()

    # Rolling 5-minute means
    out["rolling_rps_5m"] = out["requests_per_sec"].rolling(window=5, min_periods=1).mean()
    out["rolling_latency_5m"] = out["latency_ms"].rolling(window=5, min_periods=1).mean()
    out["rolling_cpu_5m"] = out["cpu_usage"].rolling(window=5, min_periods=1).mean()

    # Momentum & Velocity
    out["traffic_growth_rate"] = (
        (out["requests_per_sec"] - out["rps_lag_5"]) / np.maximum(out["rps_lag_5"], 1.0)
    ).fillna(0.0)

    err_lag_5 = out["error_rate"].shift(5).bfill()
    out["error_growth_rate"] = ((out["error_rate"] - err_lag_5) / np.maximum(err_lag_5, 0.001)).fillna(0.0)

    return out


def construct_forecasting_targets(
    df: pd.DataFrame,
    horizons: Tuple[int, ...] = (5, 10, 15),
) -> pd.DataFrame:
    """Construct future forecasting targets for CPU, Latency, and RPS across horizons.

    Targets are shifted backward in time so that row t contains labels for t+h:
    - cpu_{h}m: CPU utilization at t+h
    - latency_{h}m: Latency in ms at t+h
    - rps_{h}m: RPS arrival rate at t+h
    - safe_capacity: Existing ground-truth safe capacity at time t

    Args:
        df: Input DataFrame with telemetry columns.
        horizons: Forecasting horizons in minutes (default 5, 10, 15).

    Returns:
        DataFrame with target columns appended.
    """
    out = df.copy()

    for h in horizons:
        out[f"cpu_{h}m"] = out["cpu_usage"].shift(-h)
        out[f"latency_{h}m"] = out["latency_ms"].shift(-h)
        out[f"rps_{h}m"] = out["requests_per_sec"].shift(-h)

    # safe_capacity is preserved at current time t
    if "safe_capacity" not in out.columns and "target_capacity" in out.columns:
        out["safe_capacity"] = out["target_capacity"]

    return out


def load_dataset(
    data_dir: Union[str, Path] = "Module1_Data",
    prefer_master: bool = True,
) -> pd.DataFrame:
    """Load historical telemetry dataset from master clean CSV or split files.

    Args:
        data_dir: Directory containing Module 1 CSV files.
        prefer_master: If True, load dataset_clean.csv/master_clean.csv;
                       otherwise load and concatenate [train.csv, validation.csv, test.csv].

    Returns:
        Chronologically sorted master DataFrame.
    """
    path = Path(data_dir)
    master_file = path / "dataset_clean.csv"
    if not master_file.exists():
        master_file = path / "master_clean.csv"

    if prefer_master and master_file.exists():
        df = pd.read_csv(master_file)
    else:
        train_path = path / "train.csv"
        val_path = path / "validation.csv"
        test_path = path / "test.csv"
        if not train_path.exists() or not val_path.exists() or not test_path.exists():
            raise FileNotFoundError(f"Missing training splits in directory {data_dir}")
        df_train = pd.read_csv(train_path)
        df_val = pd.read_csv(val_path)
        df_test = pd.read_csv(test_path)
        df = pd.concat([df_train, df_val, df_test], ignore_index=True)

    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values("timestamp").reset_index(drop=True)
    return df


def prepare_supervised_splits(
    data_dir: Union[str, Path] = "Module1_Data",
    validation_start: str = "2025-07-06 00:00:00",
    test_start: str = "2025-07-09 00:00:00",
    drop_target_nans: bool = True,
) -> Dict[str, Tuple[pd.DataFrame, pd.DataFrame]]:
    """End-to-end dataset pipeline: loads, engineers features and targets, and splits chronologically.

    Enforces zero future data leakage:
    - Lag/rolling features strictly use past windows.
    - Targets are shifted into future windows.
    - Chronological splits guarantee that train < validation < test.

    Returns:
        Dictionary with keys 'train', 'validation', 'test'.
        Each entry is a tuple of (X_df, y_df) with no NaNs.
    """
    df = load_dataset(data_dir=data_dir)
    df_feat = compute_lag_and_rolling_features(df)
    df_full = construct_forecasting_targets(df_feat)

    if drop_target_nans:
        # Only drops the terminal rows (e.g. last 15 mins of test) where t+15 has no ground truth
        df_full = df_full.dropna(subset=TARGET_COLUMNS).copy()

    val_ts = pd.to_datetime(validation_start)
    test_ts = pd.to_datetime(test_start)

    train_mask = df_full["timestamp"] < val_ts
    val_mask = (df_full["timestamp"] >= val_ts) & (df_full["timestamp"] < test_ts)
    test_mask = df_full["timestamp"] >= test_ts

    splits: Dict[str, Tuple[pd.DataFrame, pd.DataFrame]] = {}
    for name, mask in [("train", train_mask), ("validation", val_mask), ("test", test_mask)]:
        sub = df_full.loc[mask].reset_index(drop=True)
        X_df = sub[FEATURE_COLUMNS].copy()
        y_df = sub[TARGET_COLUMNS].copy()
        splits[name] = (X_df, y_df)

    return splits


def extract_features_from_live(
    raw: RawTelemetry,
    derived: DerivedFeatures,
) -> np.ndarray:
    """Extract a 20-dimensional feature vector from live M1 telemetry for online prediction.

    Args:
        raw: Live 15-signal raw telemetry payload.
        derived: Live 9-feature derived lag/rolling payload.

    Returns:
        2D numpy array of shape (1, 20) in exact FEATURE_COLUMNS order.
    """
    try:
        dt = datetime.fromisoformat(raw.timestamp)
    except Exception:
        dt = datetime.now(timezone.utc)

    hour = float(dt.hour)
    day_of_week = float(dt.weekday())
    is_weekend = 1.0 if dt.weekday() >= 5 else 0.0

    # Determine if observation is within result rush or calendar spike
    date_str = dt.strftime("%Y-%m-%d")
    if date_str in RESULT_WINDOW_DATES or raw.active_users > 45000:
        is_result_window = 1.0
    else:
        is_result_window = 0.0

    # Network usage: in M1 simulation network_out carries the dominant bandwidth load
    net_usage = (
        float(raw.network_out) if hasattr(raw, "network_out") else float(getattr(raw, "network_usage", 50.0))
    )

    feature_dict: Dict[str, float] = {
        "hour": hour,
        "day_of_week": day_of_week,
        "is_weekend": is_weekend,
        "is_result_window": is_result_window,
        "concurrent_users": float(raw.active_users),
        "requests_per_sec": float(raw.requests_per_sec),
        "cpu_usage": float(raw.cpu_percent),
        "memory_usage": float(raw.ram_percent),
        "network_usage": net_usage,
        "latency_ms": float(raw.response_time),
        "error_rate": float(raw.error_rate),
        "cpu_lag_1": float(derived.cpu_lag_1),
        "cpu_lag_5": float(derived.cpu_lag_5),
        "rps_lag_1": float(derived.rps_lag_1),
        "rps_lag_5": float(derived.rps_lag_5),
        "rolling_rps_5m": float(derived.rolling_rps_5m),
        "rolling_latency_5m": float(derived.rolling_latency_5m),
        "rolling_cpu_5m": float(derived.rolling_cpu_5m),
        "traffic_growth_rate": float(derived.traffic_growth_rate),
        "error_growth_rate": float(derived.error_growth_rate),
    }

    feature_vector = np.array([[feature_dict[col] for col in FEATURE_COLUMNS]], dtype=np.float32)
    return feature_vector
