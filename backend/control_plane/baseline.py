"""PortalPulse Normal Operating Baseline Engine.

Establishes empirical normal operating baselines for connected portals before any load testing,
defining nominal boundaries, degradation warning thresholds, and critical saturation thresholds.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Dict, Optional

from pydantic import BaseModel, Field

from portalpulse_sdk.schema import UniversalTelemetry

logger = logging.getLogger("portalpulse.baseline")


class PortalBaseline(BaseModel):
    """Statistical normal baseline and degradation thresholds for a host portal."""

    portal_id: str = Field(..., description="Target portal identifier")
    established_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 baseline calculation timestamp",
    )
    # Nominal Baseline Metrics
    baseline_active_sessions: int = Field(default=1, ge=0, description="Nominal idle human/operator sessions")
    baseline_rps: float = Field(default=0.2, ge=0.0, description="Nominal background/heartbeat arrival throughput")
    baseline_p50_latency_ms: float = Field(default=1.5, ge=0.0, description="Nominal median request latency")
    baseline_p95_latency_ms: float = Field(default=2.8, ge=0.0, description="Nominal 95th percentile latency")
    baseline_p99_latency_ms: float = Field(default=4.5, ge=0.0, description="Nominal 99th percentile latency")
    baseline_cpu_percent: float = Field(default=3.5, ge=0.0, le=100.0, description="Nominal idle CPU load (%)")
    baseline_ram_percent: float = Field(default=20.0, ge=0.0, le=100.0, description="Nominal baseline RAM footprint (%)")
    baseline_error_rate: float = Field(default=0.0, ge=0.0, le=1.0, description="Nominal error rate (0% healthy)")

    # Degradation & Saturation Thresholds
    warning_p95_latency_ms: float = Field(
        default=50.0, description="Latency knee-point threshold triggering AIOps early warning"
    )
    critical_p95_latency_ms: float = Field(
        default=250.0, description="Severe latency threshold triggering emergency mitigation"
    )
    warning_cpu_percent: float = Field(default=70.0, description="CPU warning threshold")
    critical_cpu_percent: float = Field(default=85.0, description="CPU saturation threshold")
    max_sustainable_in_flight: int = Field(default=48, description="Estimated in-flight concurrency envelope")


class BaselineEngine:
    """Thread-safe registry and calculator for portal operational baselines."""

    def __init__(self) -> None:
        self._baselines: Dict[str, PortalBaseline] = {}

    def compute_baseline_from_sample(self, portal_id: str, sample: UniversalTelemetry) -> PortalBaseline:
        """Derive a baseline from an observed nominal telemetry sample."""
        p50 = sample.p50_latency_ms or sample.latency_ms or 1.5
        p95 = sample.p95_latency_ms or (p50 * 1.8)
        p99 = sample.p99_latency_ms or (p50 * 2.5)
        active_sess = sample.active_sessions if sample.active_sessions is not None else sample.active_users

        baseline = PortalBaseline(
            portal_id=portal_id,
            baseline_active_sessions=max(0, active_sess),
            baseline_rps=round(sample.requests_per_sec, 2),
            baseline_p50_latency_ms=round(p50, 1),
            baseline_p95_latency_ms=round(p95, 1),
            baseline_p99_latency_ms=round(p99, 1),
            baseline_cpu_percent=round(sample.cpu_percent, 1),
            baseline_ram_percent=round(sample.ram_percent, 1),
            baseline_error_rate=round(sample.error_rate, 4),
            warning_p95_latency_ms=round(max(40.0, p95 * 3.5), 1),
            critical_p95_latency_ms=round(max(150.0, p95 * 10.0), 1),
            warning_cpu_percent=70.0,
            critical_cpu_percent=85.0,
        )
        self._baselines[portal_id] = baseline
        return baseline

    def get_baseline(self, portal_id: str) -> Optional[PortalBaseline]:
        """Retrieve established baseline for a portal."""
        return self._baselines.get(portal_id)

    def set_baseline(self, baseline: PortalBaseline) -> None:
        """Store an explicitly computed baseline."""
        self._baselines[baseline.portal_id] = baseline


BASELINE_ENGINE = BaselineEngine()
