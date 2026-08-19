#!/usr/bin/env python3
"""Run multi-tier server saturation simulations from terminal."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from week2.team1_simulation.telemetry_synthesizer import synthesize_telemetry

if __name__ == "__main__":
    scenario = sys.argv[1] if len(sys.argv) > 1 else "Result Declaration Rush"
    users = int(sys.argv[2]) if len(sys.argv) > 2 else 9500
    pods = int(sys.argv[3]) if len(sys.argv) > 3 else 4

    print(f"🚀 Simulating Scenario: '{scenario}' with {users:,} users across {pods} pods...")
    tel = synthesize_telemetry(scenario, users, num_pods=pods)
    print("-" * 60)
    print(f"Status:            {tel['risk_state']} ({tel['action_title']})")
    print(f"Bottleneck:        {tel['bottleneck']}")
    print(f"Latency (P95):     {tel['latency']} ms (SLA: 800ms)")
    print(f"CPU Utilization:   {tel['cpu']}% per pod")
    print(f"DB Connections:    {tel['db_conns']}/{tel['db_pool_size']} ({tel['db_pool_util']}%)")
    print(f"Waiting Room:      {tel['queued_users']} queued (Est. Wait: {tel['wait_time_mins']} mins)")
    print(f"Safe Capacity:     {tel['safe_capacity']:,} concurrent users")
    print("-" * 60)
