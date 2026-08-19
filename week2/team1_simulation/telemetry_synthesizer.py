"""Week 2 Telemetry Synthesizer linking multi-parameter demand to physical server telemetry."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from week2.team1_simulation.scenario_profiles import SCENARIO_PROFILES

SLA_LATENCY = 800.0
SLA_ERROR = 0.01
SLA_CPU = 85.0


def synthesize_telemetry(
    scenario_name: str,
    concurrent_users: int,
    num_pods: int = 4,
    db_pool_size: int = 100,
    cache_hit_ratio: float = 0.70,
    waiting_room_enabled: bool = False,
    degraded_mode: bool = False,
    sla_latency: float = SLA_LATENCY,
    sla_cpu: float = SLA_CPU,
) -> dict:
    """
    Calibrated multi-tier synthetic workload model establishing physically consistent relationships
    across Application Pods, Database Connection Pool, Redis Caching, and Queueing Layers.
    """
    cfg = SCENARIO_PROFILES.get(scenario_name, SCENARIO_PROFILES["Result Declaration Rush"])
    rps_mult = cfg["rps_multiplier"]
    base_knee = cfg["knee_threshold"]
    workload = cfg["workload_intensity"] * (0.68 if degraded_mode else 1.0)

    # Effective knee capacity scales with pod count and caching efficiency
    cache_multiplier = 1.0 + (cache_hit_ratio * 0.45)
    pod_multiplier = (num_pods / 4.0) ** 0.88
    db_multiplier = min(1.3, max(0.5, db_pool_size / 100.0))
    knee = int(base_knee * pod_multiplier * cache_multiplier * db_multiplier)

    # Virtual Waiting Room traffic shedding
    if waiting_room_enabled and concurrent_users > knee:
        admitted_users = int(knee * 1.05)
        queued_users = concurrent_users - admitted_users
    else:
        admitted_users = int(concurrent_users)
        queued_users = 0

    # 1. Requests per second
    raw_rps = float(round(concurrent_users * rps_mult, 1))
    admitted_rps = float(round(admitted_users * rps_mult, 1))

    # 2. CPU Utilization (per pod)
    load_per_pod = admitted_users / max(num_pods, 1)
    base_cpu = 14.0
    nominal_pod_capacity = 3125.0
    load_ratio = load_per_pod / nominal_pod_capacity
    cpu = base_cpu + (load_ratio**1.18) * 68.0 * workload
    cpu = float(np.clip(cpu, 12.0, 100.0))

    # 3. Memory Utilization
    base_mem = 22.0
    mem = base_mem + (load_ratio**0.9) * 42.0 * (0.8 + 0.2 * workload) + (cache_hit_ratio * 12.0)
    mem = float(np.clip(mem, 18.0, 96.0))

    # 4. Network Bandwidth Utilization
    net = (admitted_rps / (450.0 * num_pods)) * 80.0 * (0.7 + 0.3 * workload)
    net = float(np.clip(net, 4.0, 98.0))

    # 5. Database Connection Pool Saturation
    db_queries_per_sec = admitted_rps * (1.0 - (cache_hit_ratio * 0.85))
    conns_needed = max(3, int(db_queries_per_sec * (0.055 if cfg["is_result_window"] else 0.030)))
    active_db_conns = min(db_pool_size, conns_needed)
    db_pool_util = (active_db_conns / float(db_pool_size)) * 100.0

    # 6. Multi-Tier Latency Breakdown
    cdn_latency = float(np.clip(6.0 + (admitted_rps / 2000.0) * 8.0, 5.0, 25.0))
    app_latency = float(np.clip(14.0 + ((cpu / 100.0) ** 2.4) * 110.0, 10.0, 800.0))

    if db_pool_util < 75.0:
        db_latency = float(np.clip(10.0 + ((db_pool_util / 75.0) ** 1.8) * 45.0, 8.0, 90.0))
    else:
        overshoot_db = (db_pool_util - 75.0) / 25.0
        db_latency = float(np.clip(55.0 + (overshoot_db**2.8) * 4200.0, 55.0, 6500.0))

    network_latency = float(np.clip(10.0 + (net / 100.0) * 18.0, 8.0, 40.0))
    total_latency = float(np.clip(cdn_latency + app_latency + db_latency + network_latency, 25.0, 8000.0))

    # 7. Safe Capacity Calculation
    base_cap = 7800.0 if cfg["is_result_window"] == 1 else 9400.0
    safe_cap = max(3200.0, (base_cap * pod_multiplier * cache_multiplier * db_multiplier) - (cpu - 20.0) * 8.5)
    safe_cap = round(safe_cap, 0)

    # 8. Headroom & Utilization
    util = (concurrent_users / max(safe_cap, 1.0)) * 100.0
    headroom = int(safe_cap - concurrent_users)

    # 9. Waiting Room Est. Wait Time
    if queued_users > 0:
        drain_rate_per_min = max(admitted_rps * 60.0 * 0.4, 100.0)
        wait_time_mins = round(queued_users / drain_rate_per_min, 1)
    else:
        wait_time_mins = 0.0

    # 10. Error Rate
    if total_latency < sla_latency and cpu < sla_cpu and db_pool_util < 90.0:
        error_rate = 0.0004 + (total_latency / sla_latency) * 0.0012
    else:
        excess = max(
            (total_latency - sla_latency) / 7200.0,
            (cpu - sla_cpu) / 15.0,
            (db_pool_util - 90.0) / 10.0,
        )
        error_rate = 0.01 + (excess**1.6) * 0.65
    error_rate = float(np.clip(error_rate, 0.0001, 0.70))

    # 11. Deterministic State & Bottleneck Root Cause
    if db_pool_util >= 92.0:
        bottleneck = "Database Connection Pool Saturation 🗄️"
    elif cpu >= sla_cpu:
        bottleneck = "Application Pod CPU Exhaustion 🖥️"
    elif total_latency >= sla_latency:
        bottleneck = "Queuing Saturation Knee Breached ⚡"
    elif net >= 90.0:
        bottleneck = "Network Bandwidth Egress Limit 🌐"
    else:
        bottleneck = "Nominal Balanced Headroom (No Bottleneck) 🛡️"

    if cpu >= sla_cpu or total_latency >= sla_latency or util >= 90.0 or db_pool_util >= 90.0:
        risk_state = "CRITICAL"
        risk_color = "#EF4444"
        action_title = "PROTECT MODE ACTIVATED"
        action_desc = "Action: Active Queueing, Database Pool Throttling & Load Shedding"
    elif util >= 70.0 or db_pool_util >= 70.0:
        risk_state = "WARNING"
        risk_color = "#F59E0B"
        action_title = "PREPARE MODE ARMED"
        action_desc = "Action: Rate Limiting, Pre-warming Pods & Virtual Waiting Room Standby"
    else:
        risk_state = "SAFE"
        risk_color = "#10B981"
        action_title = "MONITOR MODE ACTIVE"
        action_desc = "Action: Standard Traffic Ingestion & Normal Throughput"

    return {
        "scenario": scenario_name,
        "users": concurrent_users,
        "admitted_users": admitted_users,
        "queued_users": queued_users,
        "wait_time_mins": wait_time_mins,
        "rps": raw_rps,
        "admitted_rps": admitted_rps,
        "cpu": round(cpu, 1),
        "mem": round(mem, 1),
        "net": round(net, 1),
        "db_conns": active_db_conns,
        "db_pool_size": db_pool_size,
        "db_pool_util": round(db_pool_util, 1),
        "latency": round(total_latency, 1),
        "cdn_latency": round(cdn_latency, 1),
        "app_latency": round(app_latency, 1),
        "db_latency": round(db_latency, 1),
        "net_latency": round(network_latency, 1),
        "error_rate": round(error_rate, 5),
        "safe_capacity": safe_cap,
        "utilization": round(util, 1),
        "headroom": headroom,
        "risk_state": risk_state,
        "risk_color": risk_color,
        "action_title": action_title,
        "action_desc": action_desc,
        "bottleneck": bottleneck,
        "knee": knee,
        "num_pods": num_pods,
        "cache_hit_ratio": cache_hit_ratio,
        "waiting_room_enabled": waiting_room_enabled,
        "degraded_mode": degraded_mode,
    }
