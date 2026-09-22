"""FastAPI HTTP routes for PortalPulse Module 9: MLOps Drift Detection & Governance."""

from __future__ import annotations

from fastapi import APIRouter

from backend.m9_mlops_drift.drift_detector import DRIFT_GOVERNANCE
from backend.m9_mlops_drift.schema import (
    DriftReportResponse,
    ModelRegistryResponse,
)

router = APIRouter(prefix="/api/v1/mlops", tags=["Module 9: MLOps Drift & Model Governance"])


@router.get(
    "/drift",
    response_model=DriftReportResponse,
    summary="Evaluate Kolmogorov-Smirnov statistical drift and Population Stability Index (PSI)",
)
def get_live_drift_report() -> DriftReportResponse:
    """Compares live sliding-window observations against training baselines across 5 telemetry features."""
    return DRIFT_GOVERNANCE.evaluate_live_drift()


@router.get(
    "/model-registry",
    response_model=ModelRegistryResponse,
    summary="List all production models, versions, benchmark metrics, and hardware targets",
)
@router.get(
    "/models",
    response_model=ModelRegistryResponse,
    include_in_schema=False,
)
def get_model_registry() -> ModelRegistryResponse:
    """Catalog of all active AI/ML models across the PortalPulse platform."""
    return DRIFT_GOVERNANCE.get_model_registry()
