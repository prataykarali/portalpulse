"""PortalPulse Module 2: Multi-Horizon Telemetry Prediction Schemas.

Defines Pydantic models for multi-horizon forecasting targets (+5m, +10m, +15m),
Capacity Pressure Index (CPI), SLA risk classifications, and production inference payloads.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List

from pydantic import BaseModel, Field


class ForecastHorizonName(str, Enum):
    """Supported multi-step forecast horizon offsets."""

    PLUS_5M = "5m"
    PLUS_10M = "10m"
    PLUS_15M = "15m"


class RiskLevel(str, Enum):
    """Operational risk level based on capacity pressure and SLA margins."""

    SAFE = "SAFE"
    AT_RISK = "AT_RISK"
    OVERLOADED = "OVERLOADED"


class ForecastHorizon(BaseModel):
    """Forecasted telemetry state for a single future time horizon."""

    horizon_minutes: int = Field(..., ge=1, le=60, description="Offset in minutes into future")
    cpu_percent: float = Field(..., ge=0.0, le=100.0, description="Forecasted CPU utilization (%)")
    latency_ms: float = Field(..., ge=0.0, description="Forecasted round-trip response time (ms)")
    requests_per_sec: float = Field(..., ge=0.0, description="Forecasted request arrival rate (RPS)")


class ForecastResult(BaseModel):
    """Consolidated multi-horizon telemetry prediction payload.

    Provides flat fields for fast programmatic access (+5m, +10m, +15m) as well as
    structured horizon dictionaries, capacity pressure index (CPI), and risk assessment.
    """

    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 UTC timestamp of the prediction",
    )
    # CPU Forecasts
    cpu_5m: float = Field(..., ge=0.0, le=100.0, description="Forecasted CPU (%) at +5 min")
    cpu_10m: float = Field(..., ge=0.0, le=100.0, description="Forecasted CPU (%) at +10 min")
    cpu_15m: float = Field(..., ge=0.0, le=100.0, description="Forecasted CPU (%) at +15 min")

    # Latency Forecasts
    latency_5m: float = Field(..., ge=0.0, description="Forecasted latency (ms) at +5 min")
    latency_10m: float = Field(..., ge=0.0, description="Forecasted latency (ms) at +10 min")
    latency_15m: float = Field(..., ge=0.0, description="Forecasted latency (ms) at +15 min")

    # RPS Forecasts
    rps_5m: float = Field(..., ge=0.0, description="Forecasted RPS at +5 min")
    rps_10m: float = Field(..., ge=0.0, description="Forecasted RPS at +10 min")
    rps_15m: float = Field(..., ge=0.0, description="Forecasted RPS at +15 min")

    # Capacity & Pressure Assessment
    safe_capacity: float = Field(..., ge=0.0, description="Forecasted safe concurrent user capacity")
    capacity_pressure_index: float = Field(
        ...,
        ge=0.0,
        description="Ratio of active users to safe capacity (current_users / safe_capacity)",
    )
    risk_level: RiskLevel = Field(..., description="Operational risk class (SAFE, AT_RISK, OVERLOADED)")
    headroom_percent: float = Field(
        ...,
        description="Remaining safe user headroom percentage before reaching SLA capacity knee",
    )

    # Structured Horizon Access
    horizons: Dict[str, ForecastHorizon] = Field(
        default_factory=dict,
        description="Grouped dictionary mapping horizon label ('5m', '10m', '15m') to ForecastHorizon",
    )

    # Runtime Telemetry
    inference_latency_ms: float = Field(
        default=0.0,
        ge=0.0,
        description="Latency overhead of forecaster inference in milliseconds (< 2.0ms)",
    )
    model_version: str = Field(
        default="2.0.0-xgboost-multi-horizon",
        description="Identifier of the serving model artifact",
    )


class MetricAccuracy(BaseModel):
    """Evaluation metrics for an individual target variable."""

    mae: float = Field(..., description="Mean Absolute Error")
    rmse: float = Field(..., description="Root Mean Squared Error")
    r2: float = Field(..., description="Coefficient of Determination (R2 Score)")


class ForecasterMetadata(BaseModel):
    """Metadata schema persisted with the trained model artifact."""

    model_name: str
    model_version: str
    created_at: str
    feature_names: List[str]
    target_names: List[str]
    hyperparameters: Dict[str, Any]
    test_metrics: Dict[str, MetricAccuracy]
    validation_metrics: Dict[str, MetricAccuracy]
    overall_test_r2: float
    safe_capacity_test_r2: float
    inference_latency_p95_ms: float
