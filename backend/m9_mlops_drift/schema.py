"""Pydantic schemas for PortalPulse Module 9: MLOps Drift Detection & Governance."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import List

from pydantic import BaseModel, Field


class DriftStatus(str, Enum):
    HEALTHY = "HEALTHY"
    MONITOR = "MONITOR"
    RETRAIN_RECOMMENDED = "RETRAIN_RECOMMENDED"


class FeatureDriftResult(BaseModel):
    """Statistical distribution shift metrics for a single monitored feature."""

    feature_name: str
    ks_statistic: float = Field(..., ge=0.0, le=1.0, description="Kolmogorov-Smirnov distance D")
    p_value: float = Field(..., ge=0.0, le=1.0, description="KS two-sample p-value")
    psi_score: float = Field(..., ge=0.0, description="Population Stability Index")
    is_drifted: bool = Field(..., description="True if KS p < 0.01 or PSI >= 0.25")
    drift_status: DriftStatus
    baseline_mean: float
    current_mean: float


class DriftReportResponse(BaseModel):
    """Consolidated platform-wide MLOps drift evaluation report."""

    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    overall_status: DriftStatus
    drifted_features_count: int
    features: List[FeatureDriftResult]
    estimated_model_accuracy_pct: float
    recommended_action: str


class ModelRegistryEntry(BaseModel):
    """Metadata documenting a production model registered in PortalPulse."""

    model_id: str
    module_name: str
    model_family: str
    version: str
    artifact_path: str
    accuracy_metric: str
    accuracy_value: float
    single_sample_latency_ms: float
    hardware_target: str
    status: str


class ModelRegistryResponse(BaseModel):
    """Catalog of all production models deployed across PortalPulse modules."""

    total_models: int
    models: List[ModelRegistryEntry]
