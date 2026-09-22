"""PortalPulse Module 3: Unsupervised Isolation Forest Anomaly Detection Engine.

Wraps scikit-learn's IsolationForest trained on SLA-preserving nominal telemetry
to compute continuous normalized anomaly scores in [0.0, 1.0], detect anomalies,
and extract top contributing metric deviations.
"""

from __future__ import annotations

import os
import pickle
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import numpy as np
from sklearn.ensemble import IsolationForest

from backend.m1_monitoring.schema import RawTelemetry
from backend.m3_anomaly_rca.schema import AnomalyResult, AnomalySeverity

ANOMALY_FEATURE_NAMES: List[str] = [
    "cpu_percent",
    "ram_percent",
    "requests_per_sec",
    "response_time",
    "error_rate",
    "db_latency",
    "db_connections",
    "queue_length",
]

DEFAULT_MODEL_PATH = Path(os.environ.get("M3_MODEL_PATH", str(Path(__file__).resolve().parent / "models" / "isolation_forest.pkl")))


class IsolationForestAnomalyDetector:
    """Production Isolation Forest Anomaly Detector.

    Feature space:
      [cpu_percent, ram_percent, requests_per_sec, response_time, error_rate,
       db_latency, db_connections, queue_length]
    """

    def __init__(
        self,
        model: Optional[IsolationForest] = None,
        feature_means: Optional[Dict[str, float]] = None,
        feature_stds: Optional[Dict[str, float]] = None,
        threshold: float = 0.45,
    ) -> None:
        self.model = model or IsolationForest(
            n_estimators=150,
            contamination=0.03,
            max_samples="auto",
            random_state=42,
            n_jobs=-1,
        )
        self.threshold = threshold
        self.feature_names = ANOMALY_FEATURE_NAMES
        self.feature_means: Dict[str, float] = feature_means or {
            "cpu_percent": 38.0,
            "ram_percent": 42.0,
            "requests_per_sec": 450.0,
            "response_time": 65.0,
            "error_rate": 0.0015,
            "db_latency": 28.0,
            "db_connections": 32.0,
            "queue_length": 2.0,
        }
        self.feature_stds: Dict[str, float] = feature_stds or {
            "cpu_percent": 12.0,
            "ram_percent": 8.0,
            "requests_per_sec": 180.0,
            "response_time": 35.0,
            "error_rate": 0.0015,
            "db_latency": 10.0,
            "db_connections": 12.0,
            "queue_length": 4.0,
        }
        self.is_fitted: bool = model is not None

    @property
    def is_ready(self) -> bool:
        """Whether model weights are loaded and ready for online inference."""
        return self.is_fitted

    @property
    def model_path(self) -> Path:
        """Path to model artifact on disk."""
        return DEFAULT_MODEL_PATH

    def fit(self, X: np.ndarray[Any, Any], feature_names: Optional[List[str]] = None) -> None:
        """Fit IsolationForest on nominal telemetry samples."""
        if feature_names:
            self.feature_names = feature_names

        self.model.fit(X)
        self.is_fitted = True

        # Calculate baseline means and standard deviations for attribution
        means = np.mean(X, axis=0)
        stds = np.std(X, axis=0)
        stds = np.where(stds < 1e-6, 1.0, stds)

        for i, name in enumerate(self.feature_names):
            self.feature_means[name] = float(means[i])
            self.feature_stds[name] = float(stds[i])

    def extract_features(
        self, telemetry: Union[RawTelemetry, Dict[str, float], List[float]]
    ) -> np.ndarray[Any, Any]:
        """Transform diverse telemetry formats into 1x8 numpy feature vector."""
        if isinstance(telemetry, RawTelemetry):
            vector = [
                float(telemetry.cpu_percent),
                float(telemetry.ram_percent),
                float(telemetry.requests_per_sec),
                float(telemetry.response_time),
                float(telemetry.error_rate),
                float(telemetry.db_latency),
                float(telemetry.db_connections),
                float(telemetry.queue_length),
            ]
        elif isinstance(telemetry, dict):
            vector = [
                float(telemetry.get("cpu_percent", telemetry.get("cpu", 35.0))),
                float(telemetry.get("ram_percent", telemetry.get("ram", 40.0))),
                float(telemetry.get("requests_per_sec", telemetry.get("rps", 400.0))),
                float(telemetry.get("response_time", telemetry.get("latency", 60.0))),
                float(telemetry.get("error_rate", telemetry.get("errors", 0.001))),
                float(telemetry.get("db_latency", 25.0)),
                float(telemetry.get("db_connections", 30.0)),
                float(telemetry.get("queue_length", 0.0)),
            ]
        elif isinstance(telemetry, list):
            if len(telemetry) != len(self.feature_names):
                raise ValueError(
                    f"Expected {len(self.feature_names)} features, received {len(telemetry)}"
                )
            vector = [float(v) for v in telemetry]
        else:
            raise TypeError(f"Unsupported telemetry input type: {type(telemetry)}")

        return np.array([vector], dtype=np.float32)

    def detect(
        self, telemetry: Union[RawTelemetry, Dict[str, float], List[float]]
    ) -> AnomalyResult:
        """Evaluate anomaly status and compute normalized continuous score."""
        start_time = time.perf_counter()
        X = self.extract_features(telemetry)

        # Decision function: positive for normal, negative for anomaly
        # Typically values range between [-0.5, 0.25]
        raw_decision: float = float(self.model.decision_function(X)[0])

        # Sigmoidal mapping centered at decision boundary to [0.0, 1.0]
        # raw_decision > 0 => score < 0.50 (nominal)
        # raw_decision = 0 => score = 0.50 (threshold boundary)
        # raw_decision < 0 => score > 0.50 (anomalous)
        k = 18.0
        anomaly_score = float(1.0 / (1.0 + np.exp(k * raw_decision)))
        anomaly_score = round(max(0.0, min(1.0, anomaly_score)), 4)

        is_anomaly = anomaly_score >= self.threshold

        if anomaly_score >= 0.70:
            severity = AnomalySeverity.CRITICAL.value
        elif anomaly_score >= self.threshold:
            severity = AnomalySeverity.WARNING.value
        else:
            severity = AnomalySeverity.NOMINAL.value

        # Identify top contributing metrics based on z-score deviation
        contributing: List[Dict[str, Any]] = []
        feature_vals = X[0]
        for i, name in enumerate(self.feature_names):
            val = float(feature_vals[i])
            mean = self.feature_means.get(name, val)
            std = self.feature_stds.get(name, 1.0)
            z_score = (val - mean) / (std if std > 1e-6 else 1.0)

            if abs(z_score) >= 1.75:
                contributing.append(
                    {
                        "metric": name,
                        "value": round(val, 4),
                        "baseline_mean": round(mean, 2),
                        "z_score": round(float(z_score), 2),
                    }
                )

        contributing.sort(key=lambda x: abs(float(x["z_score"])), reverse=True)
        inference_time_ms = round((time.perf_counter() - start_time) * 1000.0, 3)

        return AnomalyResult(
            is_anomaly=is_anomaly,
            anomaly_score=anomaly_score,
            raw_decision_score=round(raw_decision, 4),
            severity=severity,
            contributing_metrics=contributing,
            inference_time_ms=inference_time_ms,
        )

    # Alias for uniform predict interface
    predict = detect


    def save(self, filepath: Optional[Path] = None) -> None:
        """Serialize model artifact and metadata to disk."""
        target = filepath or DEFAULT_MODEL_PATH
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "model": self.model,
            "threshold": self.threshold,
            "feature_names": self.feature_names,
            "feature_means": self.feature_means,
            "feature_stds": self.feature_stds,
        }
        with open(target, "wb") as f:
            pickle.dump(payload, f)

    @classmethod
    def load(cls, filepath: Optional[Path] = None) -> IsolationForestAnomalyDetector:
        """Deserialize trained model artifact from disk."""
        target = filepath or DEFAULT_MODEL_PATH
        if not target.exists():
            # Return fresh detector with default parameters
            return cls()
        with open(target, "rb") as f:
            payload = pickle.load(f)  # nosec B301
        return cls(
            model=payload.get("model"),
            feature_means=payload.get("feature_means"),
            feature_stds=payload.get("feature_stds"),
            threshold=payload.get("threshold", 0.45),
        )


# Global singleton detector instance
DETECTOR = IsolationForestAnomalyDetector.load()
ANOMALY_DETECTOR = DETECTOR
