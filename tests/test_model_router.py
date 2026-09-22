"""Unit tests for Model Arbitration Layer, Multi-Model Router & Uncertainty Estimation."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from week2.team2_ml.model_router import MODEL_ROUTER


class TestModelRouter(unittest.TestCase):
    def test_model_router_inference(self):
        res = MODEL_ROUTER.predict(
            hour=14,
            day_of_week=2,
            is_weekend=0,
            is_result_window=1,
            concurrent_users=8000,
            requests_per_sec=1200.0,
        )
        self.assertIn("consensus_capacity", res)
        self.assertIn("primary_prediction", res)
        self.assertGreater(res["consensus_capacity"], 2000.0)
        self.assertLess(res["consensus_capacity"], 15000.0)

    def test_all_5_model_architectures_present(self):
        res = MODEL_ROUTER.predict(concurrent_users=5000, requests_per_sec=600.0)
        breakdown = res["model_breakdown"]
        expected_models = [
            "XGBoost",
            "HistGradientBoosting",
            "PyTorch_MLP",
            "RandomForest",
            "Ridge",
        ]
        for m in expected_models:
            self.assertIn(m, breakdown)
            self.assertGreater(breakdown[m]["prediction"], 0)
            self.assertGreater(breakdown[m]["weight"], 0)

    def test_agreement_and_variance(self):
        res = MODEL_ROUTER.predict(concurrent_users=4000, requests_per_sec=450.0)
        self.assertGreaterEqual(res["agreement_pct"], 0.0)
        self.assertLessEqual(res["agreement_pct"], 100.0)
        self.assertIn(res["variance"], ["LOW", "MODERATE", "HIGH"])

    def test_uncertainty_and_confidence_intervals(self):
        res = MODEL_ROUTER.predict(concurrent_users=6000, requests_per_sec=800.0)
        band_90 = res["confidence_band_90"]
        band_95 = res["confidence_band_95"]
        self.assertLess(band_90[0], res["consensus_capacity"])
        self.assertGreater(band_90[1], res["consensus_capacity"])
        # 95% band should be wider than 90% band
        self.assertLessEqual(band_95[0], band_90[0])
        self.assertGreaterEqual(band_95[1], band_90[1])
        self.assertGreaterEqual(res["confidence_pct"], 40.0)

    def test_inference_latency(self):
        res = MODEL_ROUTER.predict(concurrent_users=5000)
        self.assertLess(res["inference_time_ms"], 200.0)


if __name__ == "__main__":
    unittest.main()
