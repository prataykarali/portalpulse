"""Unit tests for coupled telemetry synthesizer and queueing limits."""

import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from week2.team1_simulation.telemetry_synthesizer import synthesize_telemetry

class TestTelemetry(unittest.TestCase):
    def test_safe_zone_telemetry(self):
        tel = synthesize_telemetry("Regular Academic Day", 1500, num_pods=4)
        self.assertEqual(tel["risk_state"], "SAFE")
        self.assertLess(tel["latency"], 800.0)
        self.assertLess(tel["cpu"], 85.0)

    def test_overload_and_waiting_room(self):
        tel = synthesize_telemetry("Result Declaration Rush", 14000, num_pods=2, waiting_room_enabled=True)
        self.assertGreater(tel["queued_users"], 0)
        self.assertGreater(tel["wait_time_mins"], 0.0)

    def test_pod_scaling_impact(self):
        tel_2pods = synthesize_telemetry("Result Declaration Rush", 8000, num_pods=2)
        tel_8pods = synthesize_telemetry("Result Declaration Rush", 8000, num_pods=8)
        self.assertLess(tel_8pods["cpu"], tel_2pods["cpu"])

if __name__ == "__main__":
    unittest.main()
