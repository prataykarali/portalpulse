"""Portal Capacity Index (PCI) & Multi-Tier Headroom Engine for PortalPulse.

Calculates the operational capacity index and dynamic headroom across 5 physical bottlenecks:
1. CPU Core Capacity (Sustained 70% nominal ceiling)
2. RAM Capacity (80% memory saturation ceiling)
3. Database Connection Pool Contention (85% pool exhaustion ceiling)
4. Worker Pod Concurrency Ceiling (Max in-flight requests per worker)
5. P95 Latency SLA Ceiling (500ms response degradation knee)

Formula:
    PCI = Current Load / Sustainable Capacity
    Capacity = min(CPU_cap, RAM_cap, DB_cap, Workers_cap, SLA_cap)

Operational States:
    • SAFE:          PCI < 0.70       (Green)
    • PREPARE:       0.70 <= PCI < 0.85 (Yellow)
    • CRITICAL:      0.85 <= PCI <= 1.00 (Orange)
    • OVER_CAPACITY: PCI > 1.00       (Red)
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

from portalpulse_sdk.schema import UniversalTelemetry

logger = logging.getLogger("portalpulse.capacity_index")


class PCIState(str, Enum):
    """Operational states for Portal Capacity Index."""

    SAFE = "SAFE"
    PREPARE = "PREPARE"
    CRITICAL = "CRITICAL"
    OVER_CAPACITY = "OVER_CAPACITY"


class CapacityBreakdown(BaseModel):
    """Individual bottleneck limits calculated from live telemetry."""

    cpu_capacity_users: int
    ram_capacity_users: int
    db_capacity_users: int
    workers_capacity_users: int
    sla_capacity_users: int


class CapacityIndexReport(BaseModel):
    """Structured report evaluating real-time Portal Capacity Index and Headroom."""

    portal_id: str
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    pci: float
    state: PCIState
    current_users: int
    sustainable_users: int
    headroom_users: int
    headroom_pct: float
    limiting_bottleneck: str
    breakdown: CapacityBreakdown
    recommendation: str


class PortalCapacityEngine:
    """Computes empirical capacity limits and dynamic headroom for connected portals."""

    def __init__(
        self,
        target_cpu_max: float = 70.0,
        target_ram_max: float = 80.0,
        target_db_util_max: float = 0.85,
        target_sla_p95_ms: float = 500.0,
        worker_concurrency_factor: int = 40,
    ) -> None:
        self.target_cpu_max = target_cpu_max
        self.target_ram_max = target_ram_max
        self.target_db_util_max = target_db_util_max
        self.target_sla_p95_ms = target_sla_p95_ms
        self.worker_concurrency_factor = worker_concurrency_factor

    def compute_capacity_index(self, telemetry: UniversalTelemetry) -> CapacityIndexReport:
        """Compute the multi-tier capacity index and find the limiting bottleneck."""
        current_users = max(1, telemetry.active_users or telemetry.active_sessions or 1)
        current_cpu = max(0.5, telemetry.cpu_percent)
        current_ram = max(1.0, telemetry.ram_percent)
        current_lat = max(1.0, telemetry.p95_latency_ms or telemetry.latency_ms or 20.0)
        current_db = max(1.0, telemetry.db_connections)
        db_limit = max(10, telemetry.db_connection_limit or 200)
        pods = max(1, telemetry.service_instances or 4)

        # 1. CPU Sustainable Capacity (nominal 70% threshold)
        cpu_cap = int(current_users * (self.target_cpu_max / current_cpu))

        # 2. RAM Sustainable Capacity (nominal 80% threshold)
        ram_cap = int(current_users * (self.target_ram_max / current_ram))

        # 3. DB Pool Capacity (85% pool allocation saturation ceiling)
        current_db_pct = max(1.0, telemetry.db_connections)
        db_cap = int(current_users * (85.0 / current_db_pct))

        # 4. Worker Capacity (Pods * concurrency factor)
        # Factor in session-to-concurrency ratio (~1:25 typical web user)
        session_to_inflight_ratio = max(1.0, float(current_users) / max(1, telemetry.concurrent_requests or 1))
        workers_cap = int(pods * self.worker_concurrency_factor * min(35.0, session_to_inflight_ratio))

        # 5. SLA Latency Capacity (Degradation knee at 500ms P95)
        # Queueing theory approximation: throughput capacity before knee
        if current_lat <= self.target_sla_p95_ms:
            lat_scale = (self.target_sla_p95_ms / current_lat) ** 0.65
            sla_cap = int(current_users * lat_scale)
        else:
            # Already violating SLA
            sla_cap = int(current_users * (self.target_sla_p95_ms / current_lat))

        # Clamp min realistic capacity
        cpu_cap = max(50, cpu_cap)
        ram_cap = max(50, ram_cap)
        db_cap = max(50, db_cap)
        workers_cap = max(50, workers_cap)
        sla_cap = max(50, sla_cap)

        bottlenecks = {
            "CPU_CORES": cpu_cap,
            "MEMORY_RAM": ram_cap,
            "DATABASE_POOL": db_cap,
            "WORKER_PODS": workers_cap,
            "LATENCY_SLA": sla_cap,
        }

        limiting_bottleneck, sustainable_users = min(bottlenecks.items(), key=lambda item: item[1])

        # Compute Portal Capacity Index (PCI)
        pci = round(current_users / max(1.0, float(sustainable_users)), 3)
        headroom_users = sustainable_users - current_users
        headroom_pct = round((headroom_users / max(1.0, float(sustainable_users))) * 100.0, 1)

        # Determine PCI State
        if pci < 0.70:
            state = PCIState.SAFE
            rec = "Operating within nominal headroom. No automated actions required."
        elif pci < 0.85:
            state = PCIState.PREPARE
            rec = f"Headroom tightening. Monitor {limiting_bottleneck}. Prepare auto-scaling or caching."
        elif pci <= 1.00:
            state = PCIState.CRITICAL
            rec = f"Approaching saturation ceiling on {limiting_bottleneck}. Recommend ENABLE_WAITING_ROOM or SCALE_OUT_WORKERS."
        else:
            state = PCIState.OVER_CAPACITY
            rec = f"OVER CAPACITY: System exceeding sustainable ceiling on {limiting_bottleneck}! Emergency waiting room engagement active."

        return CapacityIndexReport(
            portal_id=telemetry.portal_id,
            pci=pci,
            state=state,
            current_users=current_users,
            sustainable_users=sustainable_users,
            headroom_users=headroom_users,
            headroom_pct=headroom_pct,
            limiting_bottleneck=limiting_bottleneck,
            breakdown=CapacityBreakdown(
                cpu_capacity_users=cpu_cap,
                ram_capacity_users=ram_cap,
                db_capacity_users=db_cap,
                workers_capacity_users=workers_cap,
                sla_capacity_users=sla_cap,
            ),
            recommendation=rec,
        )


# Global singleton instance
CAPACITY_ENGINE = PortalCapacityEngine()
