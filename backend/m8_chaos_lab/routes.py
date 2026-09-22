"""FastAPI HTTP routes for PortalPulse Module 8: Chaos Engineering & Knee-Point Lab."""

from __future__ import annotations

from fastapi import APIRouter

from backend.m8_chaos_lab.chaos_engine import CHAOS_LAB
from backend.m8_chaos_lab.schema import (
    ChaosInjectionRequest,
    ChaosStatusResponse,
    KneePointAnalysis,
)

router = APIRouter(prefix="/api/v1/chaos", tags=["Module 8: Chaos Engineering Lab"])


@router.post(
    "/inject",
    response_model=ChaosStatusResponse,
    summary="Inject operational stress or failure scenario into platform simulator",
)
def post_inject_chaos(request: ChaosInjectionRequest) -> ChaosStatusResponse:
    """Simulates flash crowd rush, DB lock contention, CPU hotspot, memory leak, or packet drops."""
    return CHAOS_LAB.inject_chaos(request)


@router.post(
    "/recover",
    response_model=ChaosStatusResponse,
    summary="Restore platform simulator to nominal operating conditions",
)
def post_recover_platform() -> ChaosStatusResponse:
    """Cancels active chaos drill and returns simulator to baseline normal state."""
    return CHAOS_LAB.recover()


@router.get(
    "/status",
    response_model=ChaosStatusResponse,
    summary="Get current chaos drill status and timer",
)
def get_chaos_status() -> ChaosStatusResponse:
    """Returns active scenario, intensity, remaining duration, and impact summary."""
    return CHAOS_LAB.get_status()


@router.get(
    "/knee-analysis",
    response_model=KneePointAnalysis,
    summary="Analyze M/M/c queuing knee-point curvature and capacity headroom",
)
def get_knee_point_analysis() -> KneePointAnalysis:
    """Computes queuing delay inflection point and distance to exponential latency cliff."""
    return CHAOS_LAB.analyze_knee_point()
