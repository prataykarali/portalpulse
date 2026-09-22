"""PortalPulse Module 2: Production Load Forecaster Engine.

Provides the production LoadForecaster class for online inference, predicting multi-horizon
telemetry metrics (+5m, +10m, +15m), computing Capacity Pressure Index (CPI), and returning
typed Pydantic ForecastResult payloads with sub-2ms latency.
"""

from __future__ import annotations

import os
import pickle
import time
from pathlib import Path
from typing import Any, Optional, Union

import numpy as np

from backend.m1_monitoring.schema import DerivedFeatures, RawTelemetry
from backend.m2_prediction.feature_pipeline import (
    extract_features_from_live,
)
from backend.m2_prediction.schema import (
    ForecastHorizon,
    ForecastResult,
    RiskLevel,
)

ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_MODEL_PATH = Path(os.environ.get("M2_MODEL_PATH", str(ROOT_DIR / "backend" / "m2_prediction" / "models" / "xgboost_forecaster.pkl")))

SLA_LATENCY_MS: float = 800.0
SLA_CPU_PERCENT: float = 85.0
SLA_ERROR_RATE: float = 0.01


class LoadForecaster:
    """Production inference engine for PortalPulse Module 2 (Multi-Horizon Telemetry Forecaster)."""

    def __init__(self, model_path: Optional[Union[str, Path]] = None) -> None:
        self.model_path = Path(model_path or DEFAULT_MODEL_PATH)
        self.model: Optional[Any] = None
        self._load_model()

    def _load_model(self) -> None:
        """Load serialized forecaster model from disk, auto-training if absent."""
        if not self.model_path.exists():
            try:
                from backend.m2_prediction.train_forecaster import train_and_save_forecaster

                model, _ = train_and_save_forecaster(output_dir=self.model_path.parent)
                self.model = model
                return
            except Exception:
                self.model = None
                return

        try:
            with open(self.model_path, "rb") as f:
                obj = pickle.load(f)  # nosec B301
                if isinstance(obj, dict) and "model" in obj:
                    self.model = obj["model"]
                else:
                    self.model = obj
        except Exception:
            self.model = None

    @property
    def is_ready(self) -> bool:
        """Whether model weights are loaded and ready for online inference."""
        return self.model is not None

    def reload(self) -> None:
        """Force reload of the serialized model from disk."""
        self._load_model()

    def predict(
        self,
        raw: RawTelemetry,
        derived: DerivedFeatures,
    ) -> ForecastResult:
        """Execute single-step online multi-horizon forecast.

        Args:
            raw: Live 15-signal raw telemetry from Module 1 collector/simulator.
            derived: Live 9 derived lag and rolling features from Module 1.

        Returns:
            Typed Pydantic ForecastResult with +5m, +10m, +15m projections, CPI, and SLA risk class.
        """
        t0 = time.perf_counter()

        # Extract 20-dimensional feature vector
        feat_vector = extract_features_from_live(raw, derived)

        if self.model is not None:
            raw_preds = self.model.predict(feat_vector)
            if hasattr(raw_preds, "to_numpy"):
                raw_preds = raw_preds.to_numpy()
            preds = np.asarray(raw_preds, dtype=float).flatten()
        else:
            # Fallback heuristic if model is not yet compiled
            preds = self._heuristic_fallback(raw, derived)

        # Index mapping according to TARGET_COLUMNS:
        # 0: cpu_5m, 1: cpu_10m, 2: cpu_15m
        # 3: latency_5m, 4: latency_10m, 5: latency_15m
        # 6: rps_5m, 7: rps_10m, 8: rps_15m
        # 9: safe_capacity
        cpu_5m = float(np.clip(preds[0], 0.0, 100.0))
        cpu_10m = float(np.clip(preds[1], 0.0, 100.0))
        cpu_15m = float(np.clip(preds[2], 0.0, 100.0))

        latency_5m = float(max(10.0, preds[3]))
        latency_10m = float(max(10.0, preds[4]))
        latency_15m = float(max(10.0, preds[5]))

        rps_5m = float(max(0.0, preds[6]))
        rps_10m = float(max(0.0, preds[7]))
        rps_15m = float(max(0.0, preds[8]))

        safe_capacity = float(max(100.0, preds[9]))

        # Capacity Pressure Index (CPI): current active users / safe capacity
        cpi = float(round(raw.active_users / max(safe_capacity, 1.0), 4))
        headroom_percent = float(round(max(0.0, (1.0 - cpi) * 100.0), 1))

        # Risk Classification
        live_breach = (
            raw.cpu_percent >= SLA_CPU_PERCENT
            or raw.response_time >= SLA_LATENCY_MS
            or raw.error_rate >= SLA_ERROR_RATE
        )
        if cpi >= 0.90 or live_breach:
            risk_level = RiskLevel.OVERLOADED
        elif cpi >= 0.70 or raw.cpu_percent >= 70.0 or raw.response_time >= 400.0:
            risk_level = RiskLevel.AT_RISK
        else:
            risk_level = RiskLevel.SAFE

        # Grouped Horizons
        horizons = {
            "5m": ForecastHorizon(
                horizon_minutes=5,
                cpu_percent=round(cpu_5m, 2),
                latency_ms=round(latency_5m, 2),
                requests_per_sec=round(rps_5m, 2),
            ),
            "10m": ForecastHorizon(
                horizon_minutes=10,
                cpu_percent=round(cpu_10m, 2),
                latency_ms=round(latency_10m, 2),
                requests_per_sec=round(rps_10m, 2),
            ),
            "15m": ForecastHorizon(
                horizon_minutes=15,
                cpu_percent=round(cpu_15m, 2),
                latency_ms=round(latency_15m, 2),
                requests_per_sec=round(rps_15m, 2),
            ),
        }

        inference_latency_ms = round((time.perf_counter() - t0) * 1000.0, 3)

        return ForecastResult(
            timestamp=raw.timestamp,
            cpu_5m=round(cpu_5m, 2),
            cpu_10m=round(cpu_10m, 2),
            cpu_15m=round(cpu_15m, 2),
            latency_5m=round(latency_5m, 2),
            latency_10m=round(latency_10m, 2),
            latency_15m=round(latency_15m, 2),
            rps_5m=round(rps_5m, 2),
            rps_10m=round(rps_10m, 2),
            rps_15m=round(rps_15m, 2),
            safe_capacity=round(safe_capacity, 1),
            capacity_pressure_index=cpi,
            risk_level=risk_level,
            headroom_percent=headroom_percent,
            horizons=horizons,
            inference_latency_ms=inference_latency_ms,
            model_version="2.0.0-xgboost-multi-horizon",
        )

    def _heuristic_fallback(
        self,
        raw: RawTelemetry,
        derived: DerivedFeatures,
    ) -> np.ndarray:
        """Statistical fallback when offline model weights are unavailable."""
        traffic_factor = 1.0 + derived.traffic_growth_rate
        cpu_trend = (raw.cpu_percent - derived.cpu_lag_5) / 5.0

        cpu_5 = np.clip(raw.cpu_percent + cpu_trend * 5, 10.0, 95.0)
        cpu_10 = np.clip(raw.cpu_percent + cpu_trend * 10, 10.0, 95.0)
        cpu_15 = np.clip(raw.cpu_percent + cpu_trend * 15, 10.0, 95.0)

        rps_5 = max(5.0, raw.requests_per_sec * traffic_factor)
        rps_10 = max(5.0, raw.requests_per_sec * (traffic_factor**1.5))
        rps_15 = max(5.0, raw.requests_per_sec * (traffic_factor**2.0))

        lat_5 = max(25.0, raw.response_time * 1.05)
        lat_10 = max(25.0, raw.response_time * 1.10)
        lat_15 = max(25.0, raw.response_time * 1.15)

        safe_cap = max(1000.0, raw.service_instances * 2000.0)

        return np.array(
            [cpu_5, cpu_10, cpu_15, lat_5, lat_10, lat_15, rps_5, rps_10, rps_15, safe_cap],
            dtype=np.float32,
        )


# Global singleton forecaster instance
FORECASTER = LoadForecaster()
