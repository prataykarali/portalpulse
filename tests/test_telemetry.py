"""Unit tests for multi-parameter telemetry synthesizer, SLA limits, and fault injection."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from week2.team1_simulation.telemetry_synthesizer import (
    find_saturation_knee,
    synthesize_telemetry,
)


class TestTelemetrySynthesizer(unittest.TestCase):
    def test_safe_zone_telemetry(self):
        tel = synthesize_telemetry("Regular Academic Day", 1500, num_pods=4)
        self.assertEqual(tel["risk_state"], "SAFE")
        self.assertLess(tel["latency"], 800.0)
        self.assertLess(tel["cpu"], 85.0)

    def test_overload_and_waiting_room(self):
        tel = synthesize_telemetry("Result Declaration Rush", 14000, num_pods=2, waiting_room_enabled=True)
        self.assertGreater(tel["queued_users"], 0)
        self.assertGreater(tel["wait_time_mins"], 0.0)
        self.assertLess(tel["admitted_users"], 14000)

    def test_pod_scaling_impact(self):
        tel_2pods = synthesize_telemetry("Result Declaration Rush", 8000, num_pods=2)
        tel_8pods = synthesize_telemetry("Result Declaration Rush", 8000, num_pods=8)
        self.assertLess(tel_8pods["cpu"], tel_2pods["cpu"])
        self.assertLess(tel_8pods["latency"], tel_2pods["latency"])

    def test_db_lock_fault_injection(self):
        tel_normal = synthesize_telemetry("Result Declaration Rush", 6000, num_pods=4, fault_type="None")
        tel_fault = synthesize_telemetry(
            "Result Declaration Rush", 6000, num_pods=4, fault_type="DB Lock Contention"
        )
        self.assertGreater(tel_fault["db_latency"], tel_normal["db_latency"])
        self.assertIn("Fault Injected", tel_fault["bottleneck"])

    def test_network_degradation_fault(self):
        tel_net = synthesize_telemetry(
            "Regular Academic Day", 3000, num_pods=4, fault_type="Network Degradation"
        )
        self.assertGreaterEqual(tel_net["net_latency"], 350.0)
        self.assertGreater(tel_net["error_rate"], 0.01)

    def test_memory_leak_fault(self):
        tel_mem = synthesize_telemetry("Exam Fee Registration", 5000, num_pods=4, fault_type="Memory Leak")
        self.assertGreaterEqual(tel_mem["mem"], 60.0)
        self.assertIn("Memory Leak", tel_mem["bottleneck"])

    def test_all_scenarios_synthesize_cleanly(self):
        scenarios = [
            "Result Declaration Rush",
            "Regular Academic Day",
            "Exam Fee Registration",
            "Course Registration Rush",
            "Off-Peak Night",
        ]
        for sc in scenarios:
            tel = synthesize_telemetry(sc, 3000, num_pods=4)
            self.assertEqual(tel["scenario"], sc)
            self.assertGreater(tel["safe_capacity"], 0)
            self.assertGreater(tel["rps"], 0)

    def test_knee_point_saturation_sweep(self):
        knee_res = find_saturation_knee(
            "Result Declaration Rush", num_pods=4, db_pool_size=100, num_points=15
        )
        self.assertIn("saturation_threshold_users", knee_res)
        self.assertGreater(knee_res["saturation_threshold_users"], 1000)
        self.assertEqual(len(knee_res["sweep_data"]), 15)


if __name__ == "__main__":
    unittest.main()
