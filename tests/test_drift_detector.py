"""Unit tests for Data Drift Monitor and MLOps PSI Calculations."""

import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from week2.team2_ml.drift_detector import DRIFT_DETECTOR


class TestDriftDetector(unittest.TestCase):
    def test_psi_calculation(self):
        base = np.random.normal(5000, 1000, 500)
        curr_identical = base.copy()
        curr_shifted = np.random.normal(12000, 2500, 500)

        psi_zero = DRIFT_DETECTOR.compute_psi(base, curr_identical)
        self.assertLess(psi_zero, 0.05)

        psi_high = DRIFT_DETECTOR.compute_psi(base, curr_shifted)
        self.assertGreater(psi_high, 0.25)

    def test_live_drift_evaluation_healthy(self):
        # Nominal in-distribution values
        res = DRIFT_DETECTOR.evaluate_live_drift(
            current_users=5500,
            current_rps=700.0,
            current_cpu=45.0,
            current_latency=180.0,
            current_db_pool=40.0,
        )
        self.assertEqual(res["status"], "HEALTHY")
        self.assertGreaterEqual(res["model_accuracy_pct"], 90.0)

    def test_live_drift_evaluation_retrain_alert(self):
        # Extreme out-of-distribution traffic
        res = DRIFT_DETECTOR.evaluate_live_drift(
            current_users=32000,
            current_rps=4200.0,
            current_cpu=96.0,
            current_latency=1400.0,
            current_db_pool=98.0,
        )
        self.assertEqual(res["status"], "RETRAIN_RECOMMENDED")
        self.assertIn("retrain", res["action_recommendation"].lower())


if __name__ == "__main__":
    unittest.main()
