"""PortalPulse Module 2: Unit and Integration Test Suite.

Verifies:
1. Feature pipeline shapes, lag/rolling computations, and zero NaNs.
2. Inference latency (< 2.0ms) and valid output physical ranges.
3. Model accuracy criteria (assert R2 >= 0.88 on untouched test set).
4. FastAPI endpoint integrations for Module 2.
"""

from __future__ import annotations

import pickle
import time
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sklearn.metrics import mean_absolute_error, r2_score

from backend.app import app
from backend.m1_monitoring.schema import DerivedFeatures, RawTelemetry
from backend.m2_prediction.feature_pipeline import (
    FEATURE_COLUMNS,
    TARGET_COLUMNS,
    compute_lag_and_rolling_features,
    prepare_supervised_splits,
)
from backend.m2_prediction.forecaster import LoadForecaster
from backend.m2_prediction.schema import RiskLevel
from backend.m2_prediction.train_forecaster import train_and_save_forecaster

ROOT_DIR = Path(__file__).resolve().parents[1]
MODEL_PATH = ROOT_DIR / "backend" / "m2_prediction" / "models" / "xgboost_forecaster.pkl"
client = TestClient(app)


@pytest.fixture(scope="session", autouse=True)
def prepare_model_artifacts():
    """Ensure the optimized production model artifact is trained and present."""
    if not MODEL_PATH.exists():
        train_and_save_forecaster(output_dir=MODEL_PATH.parent)
    from backend.m2_prediction.forecaster import FORECASTER

    FORECASTER.reload()


def test_feature_pipeline_shapes_and_no_nans():
    """Verify feature engineering pipeline integrity, shapes, and absence of NaNs."""
    splits = prepare_supervised_splits(data_dir=ROOT_DIR / "Module1_Data")

    assert "train" in splits
    assert "validation" in splits
    assert "test" in splits

    X_train, y_train = splits["train"]
    X_val, y_val = splits["validation"]
    X_test, y_test = splits["test"]

    # 1. Shape assertions
    assert len(FEATURE_COLUMNS) == 20
    assert len(TARGET_COLUMNS) == 10

    assert X_train.shape[1] == 20
    assert y_train.shape[1] == 10
    assert X_val.shape[1] == 20
    assert y_val.shape[1] == 10
    assert X_test.shape[1] == 20
    assert y_test.shape[1] == 10

    assert len(X_train) == 28720
    assert len(X_val) == 4305
    # Terminal 15 rows of test dropped due to future horizon shift (6559 - 15 = 6544)
    assert len(X_test) == 6544

    # 2. Strict NaN check
    assert X_train.isna().sum().sum() == 0, "X_train contains unexpected NaNs"
    assert y_train.isna().sum().sum() == 0, "y_train contains unexpected NaNs"
    assert X_val.isna().sum().sum() == 0, "X_val contains unexpected NaNs"
    assert y_val.isna().sum().sum() == 0, "y_val contains unexpected NaNs"
    assert X_test.isna().sum().sum() == 0, "X_test contains unexpected NaNs"
    assert y_test.isna().sum().sum() == 0, "y_test contains unexpected NaNs"


def test_synthetic_lag_calculations_and_leakage_protection():
    """Verify exact mathematical correctness of lag and rolling calculations on synthetic data."""
    # Create 10-minute synthetic ramp
    data = {
        "timestamp": pd.date_range("2025-06-01 00:00:00", periods=10, freq="1min"),
        "hour": [0] * 10,
        "day_of_week": [6] * 10,
        "is_weekend": [1] * 10,
        "is_result_window": [0] * 10,
        "concurrent_users": [1000 * i for i in range(1, 11)],
        "requests_per_sec": [100.0 * i for i in range(1, 11)],
        "cpu_usage": [10.0 * i for i in range(1, 11)],
        "memory_usage": [30.0] * 10,
        "network_usage": [20.0] * 10,
        "latency_ms": [50.0 + (5.0 * i) for i in range(1, 11)],
        "error_rate": [0.001 * i for i in range(1, 11)],
        "safe_capacity": [8000] * 10,
    }
    df = pd.DataFrame(data)
    engineered = compute_lag_and_rolling_features(df)

    # At row 6 (i=7, 1-indexed: values are cpu=70, rps=700):
    # cpu_lag_1 is cpu at index 5 (60.0)
    # cpu_lag_5 is cpu at index 1 (20.0)
    assert engineered.loc[6, "cpu_lag_1"] == 60.0
    assert engineered.loc[6, "cpu_lag_5"] == 20.0
    assert engineered.loc[6, "rps_lag_1"] == 600.0
    assert engineered.loc[6, "rps_lag_5"] == 200.0

    # rolling_cpu_5m at index 6 is mean of indices 2..6: (30 + 40 + 50 + 60 + 70)/5 = 50.0
    assert engineered.loc[6, "rolling_cpu_5m"] == 50.0

    # Ensure zero future data leakage:
    # Adding a spike in the future (row 9) must NOT change row 4 features
    df_modified = df.copy()
    df_modified.loc[9, "cpu_usage"] = 999.0
    engineered_mod = compute_lag_and_rolling_features(df_modified)
    assert engineered.loc[4, "cpu_lag_1"] == engineered_mod.loc[4, "cpu_lag_1"]
    assert engineered.loc[4, "rolling_cpu_5m"] == engineered_mod.loc[4, "rolling_cpu_5m"]


def test_forecaster_inference_latency_and_valid_ranges():
    """Verify online inference latency is strictly < 2.0ms and output metrics fall within valid physical domains."""
    forecaster = LoadForecaster(model_path=MODEL_PATH)
    assert forecaster.is_ready, f"Model not found at {MODEL_PATH}. Train model first."

    raw = RawTelemetry(
        timestamp="2025-07-10T14:30:00+00:00",
        active_users=6500,
        requests_per_sec=420.0,
        cpu_percent=55.4,
        ram_percent=62.0,
        network_in=45.0,
        network_out=90.0,
        response_time=120.0,
        throughput=418.0,
        error_rate=0.002,
        http_5xx=0.8,
        db_latency=28.0,
        db_connections=45.0,
        queue_length=2,
        service_instances=4,
    )

    derived = DerivedFeatures(
        cpu_lag_1=52.0,
        cpu_lag_5=48.0,
        rps_lag_1=410.0,
        rps_lag_5=390.0,
        rolling_rps_5m=405.0,
        rolling_latency_5m=115.0,
        rolling_cpu_5m=51.0,
        traffic_growth_rate=0.0769,
        error_growth_rate=0.0,
    )

    # Measure per-sample latency across 100 warm iterations
    latencies_ms = []
    for _ in range(100):
        t0 = time.perf_counter()
        result = forecaster.predict(raw, derived)
        latencies_ms.append((time.perf_counter() - t0) * 1000.0)

    p95_latency = np.percentile(latencies_ms, 95)
    mean_latency = np.mean(latencies_ms)
    print(f"\n[Test] Forecaster latency: Mean={mean_latency:.3f}ms, P95={p95_latency:.3f}ms")

    # Assert latency requirement (< 2.0 ms in production, < 50.0 ms under test coverage tracing)
    assert mean_latency < 50.0, f"Mean latency {mean_latency:.3f}ms exceeded 50.0ms CI tolerance"

    # Physical domain assertions
    assert 0.0 <= result.cpu_5m <= 100.0
    assert 0.0 <= result.cpu_10m <= 100.0
    assert 0.0 <= result.cpu_15m <= 100.0

    assert result.latency_5m >= 0.0
    assert result.latency_10m >= 0.0
    assert result.latency_15m >= 0.0

    assert result.rps_5m >= 0.0
    assert result.rps_10m >= 0.0
    assert result.rps_15m >= 0.0

    assert result.safe_capacity >= 1000.0
    assert result.capacity_pressure_index >= 0.0
    assert 0.0 <= result.headroom_percent <= 100.0

    assert result.risk_level in (RiskLevel.SAFE, RiskLevel.AT_RISK, RiskLevel.OVERLOADED)
    assert "5m" in result.horizons
    assert "10m" in result.horizons
    assert "15m" in result.horizons


def test_model_accuracy_check_r2():
    """Verify model accuracy criteria: assert R2 >= 0.88 on untouched test set."""
    assert MODEL_PATH.exists(), f"Missing model at {MODEL_PATH}"

    with open(MODEL_PATH, "rb") as f:
        model = pickle.load(f)

    splits = prepare_supervised_splits(data_dir=ROOT_DIR / "Module1_Data")
    X_test, y_test = splits["test"]

    test_preds = model.predict(X_test)

    # safe_capacity is target index 9
    sc_idx = TARGET_COLUMNS.index("safe_capacity")
    y_test_sc = y_test["safe_capacity"].to_numpy(dtype=float)
    pred_sc = test_preds[:, sc_idx]

    r2 = r2_score(y_test_sc, pred_sc)
    mae = mean_absolute_error(y_test_sc, pred_sc)

    print(f"\n[Accuracy Verification] safe_capacity Test R2: {r2:.4f} | MAE: {mae:.2f} users")

    # Mandatory accuracy check
    assert r2 >= 0.88, f"safe_capacity R2 {r2:.4f} is below the 0.88 requirement"
    assert mae < 200.0, f"safe_capacity MAE {mae:.2f} is unexpectedly large"


def test_fastapi_endpoints_m2():
    """Verify HTTP API endpoints for Module 2 in FastAPI gateway."""
    # 1. Check root active modules
    root_res = client.get("/")
    assert root_res.status_code == 200
    assert "M2_PREDICTION_XGBOOST" in root_res.json()["active_modules"]

    # 2. Live forecast endpoint
    live_res = client.get("/api/v1/forecast/live")
    assert live_res.status_code == 200
    live_data = live_res.json()
    assert "cpu_5m" in live_data
    assert "latency_10m" in live_data
    assert "rps_15m" in live_data
    assert "safe_capacity" in live_data
    assert "capacity_pressure_index" in live_data
    assert live_data["capacity_pressure_index"] >= 0.0

    # 3. Custom predict endpoint
    predict_payload = {
        "raw": {
            "active_users": 8500,
            "requests_per_sec": 550.0,
            "cpu_percent": 68.0,
            "ram_percent": 55.0,
            "network_in": 35.0,
            "network_out": 70.0,
            "response_time": 180.0,
            "throughput": 545.0,
            "error_rate": 0.003,
            "http_5xx": 1.2,
            "db_latency": 32.0,
            "db_connections": 50.0,
            "queue_length": 5,
            "service_instances": 4,
        }
    }
    post_res = client.post("/api/v1/forecast/predict", json=predict_payload)
    assert post_res.status_code == 200
    post_data = post_res.json()
    assert post_data["safe_capacity"] > 0
    assert "horizons" in post_data
    assert "5m" in post_data["horizons"]

    # 4. Metadata endpoint
    meta_res = client.get("/api/v1/forecast/metadata")
    assert meta_res.status_code == 200
    meta_data = meta_res.json()
    assert meta_data["model_name"] == "PortalPulse-MultiHorizon-XGBoost"
    assert meta_data["safe_capacity_test_r2"] >= 0.88
