"""Pydantic schemas for PortalPulse Module 8: Chaos Engineering & Fault Injection."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class ChaosScenario(str, Enum):
    NORMAL = "NORMAL"
    TRAFFIC_SPIKE = "TRAFFIC_SPIKE"
    DB_LATENCY = "DB_LATENCY"
    DB_CONNECTION_EXHAUSTION = "DB_CONNECTION_EXHAUSTION"
    CACHE_MISS_STORM = "CACHE_MISS_STORM"
    WORKER_FAILURE = "WORKER_FAILURE"
    CPU_PRESSURE = "CPU_PRESSURE"
    MEMORY_PRESSURE = "MEMORY_PRESSURE"
    NETWORK_LATENCY = "NETWORK_LATENCY"
    HTTP_5XX_BURST = "HTTP_5XX_BURST"
    DEPENDENCY_FAILURE = "DEPENDENCY_FAILURE"

    # Backward-compatible aliases for legacy test suite
    DATABASE_LOCK_JAM = "DATABASE_LOCK_JAM"
    RESULT_RUSH = "RESULT_RUSH"
    REDIS_FAILOVER_TIMEOUT = "REDIS_FAILOVER_TIMEOUT"
    KNEE_SATURATION_DRILL = "KNEE_SATURATION_DRILL"
    TATKAL_STAMPEDE = "TATKAL_STAMPEDE"


class ChaosInjectionRequest(BaseModel):
    """Payload to inject chaos failure scenario into platform."""

    portal_id: str = Field(default="nirantar", description="Target portal for chaos injection")
    scenario: ChaosScenario
    intensity: float = Field(default=1.0, ge=0.1, le=5.0, description="Multiplier on stress magnitude")
    duration_seconds: int = Field(default=120, ge=0, le=3600, description="Auto-recovery timer")
    inject_db_delay_ms: float = Field(default=0.0, ge=0.0)
    inject_packet_loss_pct: float = Field(default=0.0, ge=0.0, le=100.0)


class ChaosStatusResponse(BaseModel):
    """Current chaos simulation status with reality provenance."""

    portal_id: str
    active_scenario: ChaosScenario
    intensity: float
    is_active: bool
    started_at: str
    remaining_seconds: int
    system_impact_summary: str
    is_real_local_fault: bool
    provenance_tag: str  # REAL_LOCAL_FAULT or SIMULATED_FAULT


class KneePointAnalysis(BaseModel):
    """Inflection and curvature analysis for queuing knee points."""

    knee_point_rps: float = 1250.0
    knee_latency_ms: float = 450.0
    headroom_percent: float = 28.5
    curvature_d2_latency: float = 0.084
    saturation_state: str = "NOMINAL"
    sustainable_rps: float = 1100.0
    hard_saturation_rps: float = 1500.0
    current_headroom_pct: float = 28.5
    curvature_d2L_dRPS: float = 0.084
    limiting_resource: str = "WORKER_CPU_SATURATION"
    status: str = "NORMAL"
    description: str = "Operating safely below degradation knee"

