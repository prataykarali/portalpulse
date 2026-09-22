"""PortalPulse Module 2: Multi-Horizon Telemetry Prediction API Routes.

FastAPI endpoints for serving real-time forecasts, on-demand scenario predictions,
and forecaster model governance metadata.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional, cast

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.m1_monitoring.collector import COLLECTOR
from backend.m1_monitoring.portal_simulator import PortalSimulator
from backend.m1_monitoring.schema import DerivedFeatures, RawTelemetry
from backend.m2_prediction.forecaster import FORECASTER
from backend.m2_prediction.schema import ForecastResult

router = APIRouter(prefix="/api/v1/forecast", tags=["M2: Multi-Horizon Telemetry Prediction"])
SIMULATOR = PortalSimulator()

METADATA_PATH = (
    Path(__file__).resolve().parents[2] / "backend" / "m2_prediction" / "models" / "forecaster_metadata.json"
)


class CustomPredictRequest(BaseModel):
    raw: RawTelemetry
    derived: Optional[DerivedFeatures] = None


@router.get("/live", response_model=ForecastResult)
def get_live_forecast() -> ForecastResult:
    """Generate multi-horizon forecast (+5m, +10m, +15m) from current live telemetry."""
    status = COLLECTOR.get_latest_status()
    if not status:
        initial_raw = SIMULATOR.generate_step()
        status = COLLECTOR.record_telemetry(initial_raw, SIMULATOR.config.scenario_type)

    forecast = FORECASTER.predict(status.raw, status.derived)
    return forecast


@router.post("/predict", response_model=ForecastResult)
def predict_forecast(payload: CustomPredictRequest) -> ForecastResult:
    """Compute multi-horizon forecast for custom raw and derived telemetry signals."""
    derived = payload.derived
    if derived is None:
        # Fallback: estimate basic derived signals if omitted
        derived = DerivedFeatures(
            cpu_lag_1=payload.raw.cpu_percent,
            cpu_lag_5=payload.raw.cpu_percent,
            rps_lag_1=payload.raw.requests_per_sec,
            rps_lag_5=payload.raw.requests_per_sec,
            rolling_rps_5m=payload.raw.requests_per_sec,
            rolling_latency_5m=payload.raw.response_time,
            rolling_cpu_5m=payload.raw.cpu_percent,
            traffic_growth_rate=0.0,
            error_growth_rate=0.0,
        )

    return FORECASTER.predict(payload.raw, derived)


@router.get("/metadata", response_model=Dict[str, Any])
def get_forecaster_metadata() -> Dict[str, Any]:
    """Retrieve model training parameters, feature importance, and validation metrics."""
    if not METADATA_PATH.exists():
        raise HTTPException(
            status_code=404,
            detail="Model metadata not found. Please run train_forecaster.py first.",
        )
    return cast(Dict[str, Any], json.loads(METADATA_PATH.read_text()))
