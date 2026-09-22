"""Continuous Portal Health Score & User Impact Assessment Engine.

Computes real-time 0–100 composite health scores and business-focused user impact metrics
connecting technical system failure to concrete human experience:
- Users Affected
- Failed Requests
- Estimated Waiting Time
- Protected Users Delta (Before vs After Remediation)
"""

from __future__ import annotations

import math
from typing import Any, Dict, Optional
from portalpulse_sdk.schema import UniversalTelemetry


def compute_portal_health_score(
    telemetry: UniversalTelemetry,
    capacity_pci: float = 0.50,
    sla_latency_ms: float = 500.0,
) -> Dict[str, Any]:
    """Compute continuous composite Portal Health Score (0–100).
    
    Components:
    - Availability: 100 - (error_rate * 100) (Weight: 35%)
    - Latency Health: min(100, (sla_latency / max(1, p95)) * 100) (Weight: 25%)
    - Saturation Health: max(0, 100 - max(cpu, db_pool)) (Weight: 25%)
    - Capacity Headroom: max(0, min(100, (1.0 - capacity_pci) * 100)) (Weight: 15%)
    """
    err_pct = (telemetry.error_rate or 0.0) * 100.0
    avail_score = max(0.0, 100.0 - (err_pct * 10.0))

    p95 = telemetry.p95_latency_ms or telemetry.latency_ms or 20.0
    lat_score = min(100.0, (sla_latency_ms / max(10.0, p95)) * 100.0)

    cpu = telemetry.cpu_percent or 10.0
    db = telemetry.db_connections or 10.0
    sat_score = max(0.0, 100.0 - max(cpu, db))

    cap_score = max(0.0, min(100.0, (1.2 - min(1.2, capacity_pci)) * 83.3))

    composite = (avail_score * 0.35) + (lat_score * 0.25) + (sat_score * 0.25) + (cap_score * 0.15)
    score = round(max(0.0, min(100.0, composite)), 1)

    if score >= 85.0:
        status_label = "EXCELLENT"
        color = "#10B981"
    elif score >= 70.0:
        status_label = "GOOD"
        color = "#3B82F6"
    elif score >= 50.0:
        status_label = "DEGRADED"
        color = "#F59E0B"
    else:
        status_label = "CRITICAL"
        color = "#EF4444"

    return {
        "score": score,
        "status": status_label,
        "color": color,
        "components": {
            "availability_score": round(avail_score, 1),
            "latency_score": round(lat_score, 1),
            "saturation_score": round(sat_score, 1),
            "capacity_score": round(cap_score, 1),
        },
        "sla_latency_ms": sla_latency_ms,
        "observed_p95_ms": p95,
    }


def compute_user_impact(
    telemetry: UniversalTelemetry,
    waiting_room_queue: int = 0,
    active_sessions: int = 0,
    before_affected_users: Optional[int] = None,
) -> Dict[str, Any]:
    """Calculate direct human user impact metrics."""
    sessions = active_sessions or telemetry.active_sessions or telemetry.active_users or 0
    p95 = telemetry.p95_latency_ms or telemetry.latency_ms or 20.0
    err_rate = telemetry.error_rate or 0.0

    # Users experiencing degraded latency (>800ms) or dropped by waiting room
    degraded_ratio = 0.0
    if p95 > 800.0:
        degraded_ratio = min(0.9, (p95 - 800.0) / 1200.0)

    degraded_users = int(sessions * degraded_ratio)
    failed_requests = int((telemetry.requests_per_sec or 1.0) * err_rate * 60.0)  # requests/min
    affected_users = waiting_room_queue + degraded_users + int(sessions * err_rate)

    # Estimate queue waiting time
    est_wait_sec = round(waiting_room_queue * 0.8, 1) if waiting_room_queue > 0 else 0.0
    if est_wait_sec >= 60.0:
        wait_str = f"{int(est_wait_sec // 60)}m {int(est_wait_sec % 60)}s"
    else:
        wait_str = f"{int(est_wait_sec)}s"

    protected_users = 0
    if before_affected_users is not None:
        protected_users = max(0, before_affected_users - affected_users)

    return {
        "users_affected": affected_users,
        "failed_requests": failed_requests,
        "est_waiting_time_sec": est_wait_sec,
        "est_waiting_time_str": wait_str,
        "waiting_room_queue": waiting_room_queue,
        "login_success_pct": round(max(0.0, 100.0 - (err_rate * 100.0)), 1),
        "before_affected_users": before_affected_users,
        "protected_users": protected_users,
    }
