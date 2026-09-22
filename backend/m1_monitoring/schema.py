"""PortalPulse Module 1: Monitoring & Ingestion Schemas.

Defines Pydantic models for the 15 raw telemetry metrics, 9 derived lag/rolling features,
simulation scenarios, and live APM status payloads.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


class ScenarioType(str, Enum):
    """Supported simulation workload scenarios."""

    NORMAL = "NORMAL"
    RESULT_RUSH = "RESULT_RUSH"
    FEE_REGISTRATION = "FEE_REGISTRATION"
    FLASH_CROWD = "FLASH_CROWD"
    DATABASE_LOCK_JAM = "DATABASE_LOCK_JAM"
    WORKER_CPU_SATURATION = "WORKER_CPU_SATURATION"
    NETWORK_THROTTLING = "NETWORK_THROTTLING"


class RawTelemetry(BaseModel):
    """The 15 foundational raw telemetry signals recorded every interval."""

    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 UTC timestamp of the observation",
    )
    active_users: int = Field(..., ge=0, description="Active concurrent user sessions")
    requests_per_sec: float = Field(..., ge=0.0, description="HTTP arrival rate (RPS)")
    cpu_percent: float = Field(..., ge=0.0, le=100.0, description="Host / Pod CPU utilization (%)")
    ram_percent: float = Field(..., ge=0.0, le=100.0, description="Host / Pod RAM utilization (%)")
    network_in: float = Field(..., ge=0.0, description="Inbound bandwidth throughput (MB/s)")
    network_out: float = Field(..., ge=0.0, description="Outbound bandwidth throughput (MB/s)")
    response_time: float = Field(..., ge=0.0, description="Mean round-trip request latency (ms)")
    throughput: float = Field(..., ge=0.0, description="Successfully served HTTP responses per second")
    error_rate: float = Field(..., ge=0.0, le=1.0, description="Fraction of failed requests (4xx/5xx)")
    http_5xx: float = Field(..., ge=0.0, description="Rate of 5xx server errors per second")
    db_latency: float = Field(..., ge=0.0, description="Mean database query execution latency (ms)")
    db_connections: float = Field(
        ..., ge=0.0, le=100.0, description="Database connection pool saturation (%)"
    )
    queue_length: int = Field(default=0, ge=0, description="Backlog in ingress queue / waiting room")
    service_instances: int = Field(default=4, ge=1, description="Number of active worker replicas / pods")


class DerivedFeatures(BaseModel):
    """The 9 engineered lag, rolling, and momentum features used by M2, M3, and M5."""

    cpu_lag_1: float = Field(..., description="CPU utilization 1 minute ago (%)")
    cpu_lag_5: float = Field(..., description="CPU utilization 5 minutes ago (%)")
    rps_lag_1: float = Field(..., description="Arrival rate 1 minute ago (RPS)")
    rps_lag_5: float = Field(..., description="Arrival rate 5 minutes ago (RPS)")
    rolling_rps_5m: float = Field(..., description="Rolling 5-minute mean RPS")
    rolling_latency_5m: float = Field(..., description="Rolling 5-minute mean latency (ms)")
    rolling_cpu_5m: float = Field(..., description="Rolling 5-minute mean CPU (%)")
    traffic_growth_rate: float = Field(
        ...,
        description="5-minute traffic velocity factor ((RPS - RPS_lag5) / RPS_lag5)",
    )
    error_growth_rate: float = Field(..., description="5-minute error rate growth factor")


class HealthStatus(str, Enum):
    """SRE SLA Health Status."""

    NOMINAL = "NOMINAL"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class LiveTelemetryStatus(BaseModel):
    """Consolidated live payload consumed by frontend APM and downstream modules."""

    raw: RawTelemetry
    derived: DerivedFeatures
    health_status: HealthStatus
    sla_latency_breached: bool = False
    sla_cpu_breached: bool = False
    sla_error_breached: bool = False
    sla_db_breached: bool = False
    scenario: ScenarioType = ScenarioType.NORMAL
    headroom_percent: float = Field(..., description="Estimated remaining capacity headroom before SLA knee")
    message: str = "System operating within normal operating tolerances"


class ScenarioConfig(BaseModel):
    """Configuration for adjusting synthetic workload generator."""

    scenario_type: ScenarioType
    user_multiplier: float = Field(
        default=1.0, ge=0.1, le=10.0, description="Multiplier on baseline user volume"
    )
    inject_db_delay_ms: float = Field(
        default=0.0, ge=0.0, description="Artificial database query delay injection"
    )
    inject_packet_loss_pct: float = Field(
        default=0.0, ge=0.0, le=100.0, description="Artificial network degradation"
    )
    service_instances: int = Field(default=4, ge=1, le=32, description="Active backend pod replicas")
