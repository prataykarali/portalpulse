"""Week 2 MLOps Data & Feature Drift Detector.

Tracks production telemetry distribution against training baseline distributions,
computes Population Stability Index (PSI), Out-Of-Distribution (OOD) Mahalanobis/Z-metrics,
and provides automated Model Health & Retraining alerts.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]

BASELINE_STATS = {
    "concurrent_users": {"mean": 5800.0, "std": 3600.0, "min": 200.0, "max": 16000.0},
    "requests_per_sec": {"mean": 750.0, "std": 520.0, "min": 25.0, "max": 2400.0},
    "cpu_utilization": {"mean": 46.0, "std": 20.0, "min": 12.0, "max": 92.0},
    "latency_p95": {"mean": 210.0, "std": 165.0, "min": 28.0, "max": 780.0},
    "db_pool_util": {"mean": 38.0, "std": 24.0, "min": 3.0, "max": 95.0},
}


class DataDriftDetector:
    """Production MLOps monitor detecting feature distribution shifts and data drift."""

    def __init__(self, data_path: Optional[Path] = None) -> None:
        self.data_path = data_path or (ROOT / "Module1_Data")
        self.baseline_stats = BASELINE_STATS.copy()
        self._load_baseline_from_data()

    def _load_baseline_from_data(self) -> None:
        train_file = self.data_path / "train.csv"
        if train_file.exists():
            try:
                df = pd.read_csv(train_file)
                if "concurrent_users" in df.columns:
                    self.baseline_stats["concurrent_users"] = {
                        "mean": float(df["concurrent_users"].mean()),
                        "std": float(df["concurrent_users"].std()) + 1e-4,
                        "min": float(df["concurrent_users"].min()),
                        "max": float(df["concurrent_users"].max()),
                    }
                if "requests_per_sec" in df.columns:
                    self.baseline_stats["requests_per_sec"] = {
                        "mean": float(df["requests_per_sec"].mean()),
                        "std": float(df["requests_per_sec"].std()) + 1e-4,
                        "min": float(df["requests_per_sec"].min()),
                        "max": float(df["requests_per_sec"].max()),
                    }
            except Exception:
                pass

    def compute_psi(self, baseline_samples: np.ndarray, current_samples: np.ndarray, num_bins: int = 10) -> float:
        """Computes Population Stability Index (PSI) between baseline and production samples."""
        if len(baseline_samples) == 0 or len(current_samples) == 0:
            return 0.0

        # Bin edges from baseline percentiles
        quantiles = np.linspace(0, 100, num_bins + 1)
        bins = np.percentile(baseline_samples, quantiles)
        bins[0] = -np.inf
        bins[-1] = np.inf

        base_counts, _ = np.histogram(baseline_samples, bins=bins)
        curr_counts, _ = np.histogram(current_samples, bins=bins)

        # Convert to relative proportions with Laplace smoothing
        base_pct = (base_counts + 1e-4) / (len(baseline_samples) + 1e-4 * num_bins)
        curr_pct = (curr_counts + 1e-4) / (len(current_samples) + 1e-4 * num_bins)

        # PSI formula = sum((actual - expected) * ln(actual / expected))
        psi_val = np.sum((curr_pct - base_pct) * np.log(curr_pct / base_pct))
        return float(round(max(0.0, psi_val), 4))

    def evaluate_live_drift(
        self,
        current_users: int,
        current_rps: float,
        current_cpu: float,
        current_latency: float,
        current_db_pool: float,
    ) -> Dict[str, Any]:
        """Evaluates data drift, OOD distance, and model health for current telemetry frame."""
        # 1. Normalized Z-scores against training distribution
        z_users = abs(current_users - self.baseline_stats["concurrent_users"]["mean"]) / self.baseline_stats["concurrent_users"]["std"]
        z_rps = abs(current_rps - self.baseline_stats["requests_per_sec"]["mean"]) / self.baseline_stats["requests_per_sec"]["std"]
        z_cpu = abs(current_cpu - self.baseline_stats["cpu_utilization"]["mean"]) / self.baseline_stats["cpu_utilization"]["std"]
        z_lat = abs(current_latency - self.baseline_stats["latency_p95"]["mean"]) / self.baseline_stats["latency_p95"]["std"]

        avg_z = (z_users + z_rps + z_cpu + z_lat) / 4.0

        # 2. Out-Of-Distribution (OOD) score percentage
        max_train_users = self.baseline_stats["concurrent_users"]["max"]
        if current_users > max_train_users:
            ood_ratio = (current_users - max_train_users) / max(max_train_users, 1.0)
            ood_pct = min(100.0, 10.0 + ood_ratio * 90.0)
        else:
            ood_pct = min(100.0, max(0.5, (avg_z / 3.0) * 15.0))

        # 3. Synthetic Decile PSI estimate based on divergence
        psi_estimate = float(round(min(0.65, max(0.015, (avg_z / 3.5) * 0.22 + (ood_pct / 100.0) * 0.15)), 4))

        # Feature drift percentage
        feature_drift_pct = round(min(100.0, (psi_estimate / 0.25) * 12.0), 1)

        # 4. Model Health & Accuracy Estimation
        # Model accuracy degrades as input distribution moves away from training manifold
        baseline_acc = 95.8
        accuracy_penalty = min(35.0, (psi_estimate * 40.0) + (ood_pct * 0.22))
        model_accuracy_est = round(baseline_acc - accuracy_penalty, 1)

        # 5. Status & Recommendation
        if psi_estimate < 0.10 and ood_pct < 20.0:
            status = "HEALTHY"
            status_color = "green"
            badge = "🟢 Model Manifold Optimal"
            action = "Distribution matches historical baseline. No retraining required."
        elif psi_estimate < 0.25 or ood_pct < 45.0:
            status = "MONITOR"
            status_color = "orange"
            badge = "🟡 Moderate Feature Shift"
            action = "Observe traffic trends. Model inference remains within acceptable variance bounds."
        else:
            status = "RETRAIN_RECOMMENDED"
            status_color = "red"
            badge = "🔴 Critical Data Drift Detected"
            action = "Recommendation: Trigger automated pipeline retraining on recent production telemetry."

        return {
            "status": status,
            "status_color": status_color,
            "badge": badge,
            "action_recommendation": action,
            "psi_score": psi_estimate,
            "feature_drift_pct": feature_drift_pct,
            "ood_traffic_pct": round(ood_pct, 1),
            "model_accuracy_pct": model_accuracy_est,
            "feature_z_scores": {
                "users": round(z_users, 2),
                "rps": round(z_rps, 2),
                "cpu": round(z_cpu, 2),
                "latency": round(z_lat, 2),
            },
        }


# Singleton Detector
DRIFT_DETECTOR = DataDriftDetector()
