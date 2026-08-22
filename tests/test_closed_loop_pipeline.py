"""Integration tests for the complete end-to-end Closed-Loop Control System."""

import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dashboard.db import ROLE_ACCESS_TOKENS, validate_role_access_token, get_student_results
from week2.team1_simulation.protection_controller import CLOSED_LOOP_CONTROLLER


class TestClosedLoopPipeline(unittest.TestCase):
    def test_authentication_to_query_pipeline(self):
        role = validate_role_access_token(ROLE_ACCESS_TOKENS["admin"])
        self.assertEqual(role, "admin")
        res = get_student_results("2024TEST888")
        self.assertIn("found", res)

    def test_closed_loop_stabilization_trajectory(self):
        traj = CLOSED_LOOP_CONTROLLER.run_closed_loop_simulation(
            scenario_name="Result Declaration Rush",
            surge_users=13500,
            initial_pods=4,
            initial_db_pool=100,
            initial_cache_hit=0.60,
        )
        self.assertEqual(len(traj), 4)

        t0 = traj[0]
        t1 = traj[1]
        t2 = traj[2]
        t3 = traj[3]

        # Step 0 should be degraded/critical
        self.assertIn(t0["state"], ["WARNING", "CRITICAL"])
        self.assertGreater(t0["latency"], 120.0)

        # Step 1 should actuate waiting room / cache
        self.assertGreater(t1["queued_users"], 0)

        # Step 2 should scale pods
        self.assertGreater(t2["pods"], t0["pods"])
        self.assertLess(t2["cpu"], t0["cpu"])

        # Step 3 should reach stable equilibrium
        self.assertEqual(t3["state"], "SAFE")
        self.assertLess(t3["latency"], 800.0)
        self.assertLess(t3["cpu"], 85.0)


if __name__ == "__main__":
    unittest.main()
