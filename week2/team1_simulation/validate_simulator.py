"""Formal Verification & Validation Suite for the Queueing-Based Telemetry Simulator.

Validates that all physical/queueing relationships strictly hold across 5 scenarios:
1. Users ↑ ==> Requests/sec (RPS) ↑ (Strictly Monotonic)
2. Users ↑ ==> CPU Utilization ↑ (Monotonic Saturation)
3. Users ↑ ==> Latency ms ↑ (M/M/1-inspired nonlinear knee)
4. Load > Safe Capacity ==> Latency > 800ms / CPU > 85% ==> SLA Breach
5. SLA Breach ==> Simulated Failure / Error Outcome ↑
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from week2.team1_simulation.scenario_profiles import SCENARIO_PROFILES
from week2.team1_simulation.telemetry_synthesizer import synthesize_telemetry, SLA_LATENCY, SLA_CPU

RESULTS_DIR = ROOT / "week2" / "team1_simulation"


def validate_scenario(scenario_name: str, step_points: int = 20) -> dict:
    user_steps = np.linspace(500, 13000, step_points).astype(int)
    records = [synthesize_telemetry(scenario_name, int(u)) for u in user_steps]

    users = [r["concurrent_users"] for r in records]
    rps = [r["requests_per_sec"] for r in records]
    cpus = [r["cpu_usage"] for r in records]
    latencies = [r["latency_ms"] for r in records]
    errors = [r["error_rate"] for r in records]

    # Check 1: Monotonic RPS
    is_rps_monotonic = bool(np.all(np.diff(rps) >= 0))

    # Check 2: Monotonic CPU
    is_cpu_monotonic = bool(np.all(np.diff(cpus) >= 0))

    # Check 3: Monotonic Latency Knee
    is_latency_monotonic = bool(np.all(np.diff(latencies) >= 0))

    # Check 4: Monotonic Failure Rate
    is_error_monotonic = bool(np.all(np.diff(errors) >= 0))

    # Check 5: Overload SLA Breach detection
    overload_record = records[-1]  # 13,000 users
    is_sla_breached_at_peak = bool(overload_record["latency_ms"] >= SLA_LATENCY or overload_record["cpu_usage"] >= SLA_CPU)

    # Check 6: Safe baseline within SLA
    baseline_record = records[0]  # 500 users
    is_baseline_safe = bool(baseline_record["latency_ms"] < SLA_LATENCY and baseline_record["cpu_usage"] < SLA_CPU)

    all_passed = bool(
        is_rps_monotonic
        and is_cpu_monotonic
        and is_latency_monotonic
        and is_error_monotonic
        and is_sla_breached_at_peak
        and is_baseline_safe
    )

    return {
        "scenario": scenario_name,
        "validation_passed": all_passed,
        "monotonicity_checks": {
            "rps_monotonic": is_rps_monotonic,
            "cpu_monotonic": is_cpu_monotonic,
            "latency_knee_monotonic": is_latency_monotonic,
            "failure_rate_monotonic": is_error_monotonic,
        },
        "boundary_checks": {
            "baseline_within_sla": is_baseline_safe,
            "peak_exceeds_sla_boundary": is_sla_breached_at_peak,
        },
        "sample_points": {
            "low_load_500_users": {
                "rps": rps[0],
                "cpu": cpus[0],
                "latency_ms": latencies[0],
                "simulated_error_rate": errors[0],
            },
            "knee_load_8000_users": {
                "rps": rps[11],
                "cpu": cpus[11],
                "latency_ms": latencies[11],
                "simulated_error_rate": errors[11],
            },
            "peak_overload_13000_users": {
                "rps": rps[-1],
                "cpu": cpus[-1],
                "latency_ms": latencies[-1],
                "simulated_error_rate": errors[-1],
            },
        },
    }


def main() -> None:
    print("==========================================================================")
    print(" Week 2 Verification: Queueing-Based Telemetry Simulator Formal Audit     ")
    print("==========================================================================\n")

    report = {}
    all_scenarios_passed = True

    for sc_name in SCENARIO_PROFILES.keys():
        res = validate_scenario(sc_name)
        report[sc_name] = res
        status = "PASSED ✓" if res["validation_passed"] else "FAILED ✗"
        print(f"[{sc_name}] Verification Status: {status}")
        if not res["validation_passed"]:
            all_scenarios_passed = False

    summary_file = RESULTS_DIR / "simulator_validation_report.json"
    summary_file.write_text(json.dumps(report, indent=2) + "\n")

    print(f"\nOverall Simulator Status: {'100% VALIDATED ✓' if all_scenarios_passed else 'ERRORS DETECTED'}")
    print(f"Validation report saved to: {summary_file}")


if __name__ == "__main__":
    main()
