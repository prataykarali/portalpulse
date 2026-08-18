"""Week 2 Telemetry Synthesizer linking demand to physical server telemetry."""

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


def synthesize_telemetry(scenario_name: str, concurrent_users: int) -> dict:
    """Calibrated synthetic workload model establishing physically consistent relationships."""
    cfg = SCENARIO_PROFILES[scenario_name]
    rps_mult = cfg["rps_multiplier"]
    knee = cfg["knee_threshold"]
    workload = cfg["workload_intensity"]

    # 1. Requests per second
    rps = float(round(concurrent_users * rps_mult, 1))

    # 2. CPU Utilization (exponential / logistic saturation curve)
    base_cpu = 18.0
    load_ratio = concurrent_users / 12500.0
    cpu = base_cpu + (load_ratio**1.15) * 72.0 * workload
    cpu = float(np.clip(cpu, 15.0, 100.0))

    # 3. Memory Utilization (stateful session table footprint)
    base_mem = 25.0
    mem = base_mem + (load_ratio**0.9) * 45.0 * (0.8 + 0.2 * workload)
    mem = float(np.clip(mem, 20.0, 95.0))

    # 4. Network Utilization (bandwidth consumption from RPS)
    net = (rps / 1800.0) * 85.0 * (0.7 + 0.3 * workload)
    net = float(np.clip(net, 4.0, 98.0))

    # 5. Latency Curve (M/M/1-like queuing saturation knee)
    if concurrent_users < knee:
        fraction_to_knee = concurrent_users / float(knee)
        latency = 38.0 + (fraction_to_knee**2.2) * 80.0
    else:
        overshoot = (concurrent_users - knee) / max(12500.0 - knee, 100.0)
        latency = 118.0 + (overshoot**2.6) * 7882.0
    latency = float(np.clip(latency, 25.0, 8000.0))

    # 6. Observed Error Rate (System Outcome metric)
    if latency < SLA_LATENCY and cpu < SLA_CPU:
        error_rate = 0.0005 + (latency / SLA_LATENCY) * 0.0015
    else:
        excess = max((latency - SLA_LATENCY) / 7200.0, (cpu - SLA_CPU) / 15.0)
        error_rate = 0.01 + (excess**1.6) * 0.65
    error_rate = float(np.clip(error_rate, 0.0001, 0.70))

    return {
        "scenario": scenario_name,
        "hour": cfg["hour"],
        "day_of_week": cfg["day_of_week"],
        "is_weekend": int(cfg["day_of_week"] >= 5),
        "is_result_window": cfg["is_result_window"],
        "concurrent_users": int(concurrent_users),
        "requests_per_sec": rps,
        "cpu_usage": round(cpu, 1),
        "memory_usage": round(mem, 1),
        "network_usage": round(net, 1),
        "latency_ms": round(latency, 1),
        "error_rate": round(error_rate, 5),
        "knee_threshold": knee,
    }
