"""PortalPulse Module 1: Monitoring & Ingestion API Routes.

FastAPI endpoints for ingesting raw metrics, streaming live APM telemetry,
retrieving rolling history, and controlling simulation scenarios.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from fastapi import APIRouter, Query

from backend.m1_monitoring.collector import COLLECTOR
from backend.m1_monitoring.portal_simulator import SIMULATOR
from backend.m1_monitoring.schema import (
    LiveTelemetryStatus,
    RawTelemetry,
    ScenarioConfig,
)

router = APIRouter(prefix="/api/v1", tags=["M1: Monitoring & Ingestion"])



@router.post("/telemetry/ingest", response_model=LiveTelemetryStatus)
def ingest_telemetry(telemetry: RawTelemetry) -> LiveTelemetryStatus:
    """Ingest a single raw telemetry record into the ring buffer and persistent store."""
    status = COLLECTOR.record_telemetry(telemetry)
    return status


@router.get("/telemetry/live", response_model=LiveTelemetryStatus)
def get_live_telemetry() -> LiveTelemetryStatus:
    """Fetch the latest real-time telemetry, derived lag features, and SLA health status."""
    status = COLLECTOR.get_latest_status()
    if not status:
        # If buffer is empty, generate an initial step
        initial_raw = SIMULATOR.generate_step()
        status = COLLECTOR.record_telemetry(initial_raw, SIMULATOR.config.scenario_type)
    return status


@router.get("/telemetry/history", response_model=list[RawTelemetry])
def get_telemetry_history(
    limit: int = Query(default=60, ge=1, le=1800, description="Number of recent records to retrieve"),
) -> list[RawTelemetry]:
    """Retrieve rolling history of telemetry records for UI charts and downstream model lags."""
    return COLLECTOR.get_history(limit=limit)


@router.post("/portal/scenario", response_model=dict[str, Any])
def set_scenario(config: ScenarioConfig) -> dict[str, Any]:
    """Configure the active simulation workload scenario (e.g., RESULT_RUSH, DATABASE_LOCK_JAM)."""
    SIMULATOR.update_config(config)
    COLLECTOR.current_scenario = config.scenario_type
    return {
        "status": "success",
        "active_scenario": config.scenario_type.value,
        "user_multiplier": config.user_multiplier,
        "service_instances": config.service_instances,
        "message": f"Workload scenario set to {config.scenario_type.value}",
    }


@router.get("/portal/scenario", response_model=dict[str, Any])
def get_scenario() -> dict[str, Any]:
    """Get the current simulation workload scenario and runtime parameters."""
    return {
        "active_scenario": SIMULATOR.config.scenario_type.value,
        "user_multiplier": SIMULATOR.config.user_multiplier,
        "service_instances": SIMULATOR.service_instances,
        "inject_db_delay_ms": SIMULATOR.config.inject_db_delay_ms,
    }


@router.post("/portal/step", response_model=LiveTelemetryStatus)
def step_simulation() -> LiveTelemetryStatus:
    """Advance the synthetic portal simulation by one time interval and record telemetry."""
    raw = SIMULATOR.generate_step()
    status = COLLECTOR.record_telemetry(raw, SIMULATOR.config.scenario_type)
    return status


@router.post("/portal/seed", response_model=dict[str, Any])
def seed_simulation(
    steps: int = Query(default=30, ge=5, le=300, description="Number of steps to pre-populate"),
) -> dict[str, Any]:
    """Pre-populate the ring buffer with synthetic history so lag and rolling features are ready."""
    for _ in range(steps):
        raw = SIMULATOR.generate_step()
        COLLECTOR.record_telemetry(raw, SIMULATOR.config.scenario_type)

    latest = COLLECTOR.get_latest_status()
    return {
        "status": "success",
        "seeded_steps": steps,
        "current_buffer_length": len(COLLECTOR.buffer),
        "latest_health": latest.health_status.value if latest else "NOMINAL",
    }


@router.get("/telemetry/summary", response_model=dict[str, Any])
def get_telemetry_summary() -> dict[str, Any]:
    """Compute aggregate statistical summary (P50, P95, P99 latency, error rate, RPS)."""
    history = COLLECTOR.get_history(limit=120)
    if not history:
        return {"count": 0, "message": "No telemetry data recorded yet."}

    latencies = [r.response_time for r in history]
    rps_vals = [r.requests_per_sec for r in history]
    cpus = [r.cpu_percent for r in history]
    errors = [r.error_rate for r in history]
    db_lats = [r.db_latency for r in history]

    return {
        "record_count": len(history),
        "latency_p50_ms": round(float(np.percentile(latencies, 50)), 1),
        "latency_p95_ms": round(float(np.percentile(latencies, 95)), 1),
        "latency_p99_ms": round(float(np.percentile(latencies, 99)), 1),
        "mean_rps": round(float(np.mean(rps_vals)), 1),
        "peak_rps": round(float(np.max(rps_vals)), 1),
        "mean_cpu_pct": round(float(np.mean(cpus)), 1),
        "peak_cpu_pct": round(float(np.max(cpus)), 1),
        "mean_error_rate": round(float(np.mean(errors)), 4),
        "mean_db_latency_ms": round(float(np.mean(db_lats)), 1),
    }
