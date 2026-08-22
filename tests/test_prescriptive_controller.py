"""Unit tests for Prescriptive Capacity Advisor and Infrastructure Sizing."""

import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from week2.team1_simulation.protection_controller import PRESCRIPTIVE_ADVISOR


class TestPrescriptiveController(unittest.TestCase):
    def test_safe_state_prescription(self):
        advice = PRESCRIPTIVE_ADVISOR.advise(
            scenario_name="Regular Academic Day",
            concurrent_users=2000,
            num_pods=4,
            db_pool_size=100,
        )
        self.assertEqual(advice["system_state"], "SAFE")
        self.assertEqual(advice["target_pods"], 4)
        self.assertFalse(advice["recommend_waiting_room"])

    def test_critical_state_prescription(self):
        advice = PRESCRIPTIVE_ADVISOR.advise(
            scenario_name="Result Declaration Rush",
            concurrent_users=14000,
            num_pods=4,
            db_pool_size=100,
        )
        self.assertEqual(advice["system_state"], "CRITICAL")
        self.assertGreater(advice["target_pods"], 4)
        self.assertGreater(advice["target_db_pool"], 100)
        self.assertTrue(advice["recommend_waiting_room"])
        self.assertGreater(advice["estimated_new_capacity"], advice["ml_safe_capacity"])

    def test_prepare_state_prescription(self):
        advice = PRESCRIPTIVE_ADVISOR.advise(
            scenario_name="Result Declaration Rush",
            concurrent_users=7500,
            num_pods=4,
            db_pool_size=100,
        )
        self.assertIn(advice["system_state"], ["PREPARE", "SAFE", "CRITICAL"])
        self.assertGreater(advice["ml_safe_capacity"], 0)

    def test_prescriptive_action_items(self):
        advice = PRESCRIPTIVE_ADVISOR.advise(
            scenario_name="Result Declaration Rush",
            concurrent_users=12000,
            num_pods=4,
        )
        self.assertGreater(len(advice["action_items"]), 0)


if __name__ == "__main__":
    unittest.main()
