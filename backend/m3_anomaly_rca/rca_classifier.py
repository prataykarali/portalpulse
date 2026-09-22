"""PortalPulse Module 4: Supervised XGBoost Multi-Class Root Cause Analysis (RCA) Classifier.

Attributes anomalous system incidents across 8 root-cause categories:
NORMAL, TRAFFIC_SPIKE, API_CPU, DATABASE, NETWORK, MEMORY, QUEUE_OVERLOAD, DEPENDENCY_FAILURE.
Integrates with NetworkX SystemTopologyDAG to trace causal propagation across architectural tiers.
"""

from __future__ import annotations

import os
import pickle
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import numpy as np
from xgboost import XGBClassifier

from backend.m1_monitoring.schema import RawTelemetry
from backend.m3_anomaly_rca.dependency_graph import TOPOLOGY_DAG, SystemTopologyDAG
from backend.m3_anomaly_rca.schema import FailureCategory, RCAResult

CATEGORY_NAMES: List[str] = [
    FailureCategory.NORMAL.value,
    FailureCategory.TRAFFIC_SPIKE.value,
    FailureCategory.API_CPU.value,
    FailureCategory.DATABASE.value,
    FailureCategory.NETWORK.value,
    FailureCategory.MEMORY.value,
    FailureCategory.QUEUE_OVERLOAD.value,
    FailureCategory.DEPENDENCY_FAILURE.value,
]

CATEGORY_TO_IDX: Dict[str, int] = {name: i for i, name in enumerate(CATEGORY_NAMES)}
IDX_TO_CATEGORY: Dict[int, str] = {i: name for i, name in enumerate(CATEGORY_NAMES)}

CATEGORY_TIER_MAPPING: Dict[FailureCategory, str] = {
    FailureCategory.NORMAL: "system",
    FailureCategory.TRAFFIC_SPIKE: "client",
    FailureCategory.API_CPU: "worker_backend",
    FailureCategory.DATABASE: "postgresql_db",
    FailureCategory.NETWORK: "cdn_edge",
    FailureCategory.MEMORY: "worker_backend",
    FailureCategory.QUEUE_OVERLOAD: "api_gateway",
    FailureCategory.DEPENDENCY_FAILURE: "api_gateway",
}

RECOMMENDED_PLAYBOOKS: Dict[FailureCategory, str] = {
    FailureCategory.NORMAL: (
        "System operating within nominal SLO tolerances. Continue automated telemetry collection."
    ),
    FailureCategory.TRAFFIC_SPIKE: (
        "Activate Cloudflare edge rate-limiting, engage dynamic waiting room queue, "
        "and scale worker pods horizontally via HPA."
    ),
    FailureCategory.API_CPU: (
        "Scale worker backend replicas immediately, profile endpoint CPU hotspots, "
        "and divert non-critical batch processing."
    ),
    FailureCategory.DATABASE: (
        "Increase PostgreSQL connection pool ceiling, terminate long-running idle transactions, "
        "and divert read queries to replica pool."
    ),
    FailureCategory.NETWORK: (
        "Engage redundant network transit routes, inspect ingress socket queue drops, "
        "and verify edge peering links."
    ),
    FailureCategory.MEMORY: (
        "Trigger rolling restart of degraded worker pods to reclaim heap memory, "
        "and configure container memory limits."
    ),
    FailureCategory.QUEUE_OVERLOAD: (
        "Drain and scale ingress queue consumers, activate worker backpressure, "
        "and apply graceful shedding to low-priority requests."
    ),
    FailureCategory.DEPENDENCY_FAILURE: (
        "Activate circuit breaker on degraded upstream dependency, serve cached stale responses, "
        "and alert third-party service vendor."
    ),
}

RCA_FEATURE_NAMES: List[str] = [
    "cpu_percent",
    "ram_percent",
    "requests_per_sec",
    "response_time",
    "error_rate",
    "db_latency",
    "db_connections",
    "queue_length",
]

DEFAULT_MODEL_PATH = Path(os.environ.get("M4_MODEL_PATH", str(Path(__file__).resolve().parent / "models" / "xgboost_rca.pkl")))


class XGBoostRCAClassifier:
    """Production Multi-Class XGBoost Root Cause Analysis Engine."""

    def __init__(
        self,
        model: Optional[XGBClassifier] = None,
        topology_dag: Optional[SystemTopologyDAG] = None,
    ) -> None:
        self.model = model or XGBClassifier(
            objective="multi:softprob",
            num_class=8,
            n_estimators=150,
            max_depth=5,
            learning_rate=0.08,
            subsample=0.85,
            colsample_bytree=0.85,
            random_state=42,
            n_jobs=-1,
        )
        self.topology_dag = topology_dag or TOPOLOGY_DAG
        self.feature_names = RCA_FEATURE_NAMES
        self.category_names = CATEGORY_NAMES
        self.is_fitted: bool = model is not None

    @property
    def is_ready(self) -> bool:
        """Whether model weights are loaded and ready for online inference."""
        return self.is_fitted

    @property
    def model_path(self) -> Path:
        """Path to model artifact on disk."""
        return DEFAULT_MODEL_PATH

    def extract_features(
        self, telemetry: Union[RawTelemetry, Dict[str, float], List[float]]
    ) -> np.ndarray[Any, Any]:
        """Convert input telemetry into a 1x8 numpy feature vector."""
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

    def classify(
        self,
        telemetry: Union[RawTelemetry, Dict[str, float], List[float]],
        node_metrics: Optional[Dict[str, Dict[str, float]]] = None,
    ) -> RCAResult:
        """Run multi-class RCA inference and trace topological causal propagation.

        Args:
            telemetry: Raw system metrics or dictionary.
            node_metrics: Optional node-level operational metrics for graph tracing.

        Returns:
            RCAResult with primary failure category, probabilities, causal chain,
            propagation confidence, and recommended remediation.
        """
        start_time = time.perf_counter()
        X = self.extract_features(telemetry)

        # Predict multi-class probability distribution
        probabilities_array = self.model.predict_proba(X)[0]
        pred_idx = int(np.argmax(probabilities_array))
        confidence = float(probabilities_array[pred_idx])
        predicted_category = FailureCategory(IDX_TO_CATEGORY[pred_idx])

        # Format probability dictionary
        prob_dict: Dict[str, float] = {}
        for i, name in enumerate(self.category_names):
            prob_dict[name] = round(float(probabilities_array[i]), 4)

        # Trace topological causal propagation across DAG
        if node_metrics is None:
            if isinstance(telemetry, RawTelemetry):
                node_metrics = self.topology_dag.synthesize_node_metrics(telemetry)
            else:
                # Build synthetic node metrics from vector via proxy RawTelemetry
                vec = X[0]
                raw_proxy = RawTelemetry(
                    active_users=max(100, int(vec[2] * 15)),
                    requests_per_sec=float(vec[2]),
                    cpu_percent=float(vec[0]),
                    ram_percent=float(vec[1]),
                    network_in=float(vec[2] * 0.08),
                    network_out=float(vec[2] * 0.18),
                    response_time=float(vec[3]),
                    throughput=float(vec[2] * (1.0 - min(0.5, float(vec[4])))),
                    error_rate=float(vec[4]),
                    http_5xx=float(vec[2] * float(vec[4])),
                    db_latency=float(vec[5]),
                    db_connections=float(vec[6]),
                    queue_length=int(vec[7]),
                    service_instances=4,
                )
                node_metrics = self.topology_dag.synthesize_node_metrics(raw_proxy)

        # Query NetworkX DAG for root cause node, propagation path, and impact score
        dag_root, propagation_path, dag_impact = self.topology_dag.trace_root_cause(node_metrics)

        # Fallback tier from predicted category if graph did not isolate a specific degraded node
        expected_tier = CATEGORY_TIER_MAPPING.get(predicted_category, "system")
        root_cause_tier = dag_root if dag_root != "NORMAL" else expected_tier

        # If graph path is empty or single node, provide topological propagation chain for tier
        if len(propagation_path) <= 1 and predicted_category != FailureCategory.NORMAL:
            _, propagation_path, _ = self.topology_dag.trace_root_cause(
                {root_cause_tier: {"anomaly_score": 0.9}}
            )

        graph_confidence = round(max(0.1, min(1.0, (confidence * 0.6) + (dag_impact * 0.4))), 4)
        inference_time_ms = round((time.perf_counter() - start_time) * 1000.0, 3)
        recommended_mitigation = RECOMMENDED_PLAYBOOKS.get(
            predicted_category, RECOMMENDED_PLAYBOOKS[FailureCategory.NORMAL]
        )

        return RCAResult(
            primary_root_cause=predicted_category,
            confidence=round(confidence, 4),
            probabilities=prob_dict,
            root_cause_tier=root_cause_tier,
            causal_propagation_chain=propagation_path,
            graph_propagation_confidence=graph_confidence,
            inference_time_ms=inference_time_ms,
            recommended_mitigation=recommended_mitigation,
        )

    # Alias for uniform diagnose interface
    diagnose = classify


    def save(self, filepath: Optional[Path] = None) -> None:
        """Persist trained XGBoost model to disk."""
        target = filepath or DEFAULT_MODEL_PATH
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "wb") as f:
            pickle.dump(self.model, f)

    @classmethod
    def load(
        cls,
        filepath: Optional[Path] = None,
        topology_dag: Optional[SystemTopologyDAG] = None,
    ) -> XGBoostRCAClassifier:
        """Load trained model artifact from disk."""
        target = filepath or DEFAULT_MODEL_PATH
        if not target.exists():
            return cls(topology_dag=topology_dag)
        with open(target, "rb") as f:
            model = pickle.load(f)  # nosec B301
        return cls(model=model, topology_dag=topology_dag)


# Global singleton RCA classifier instance
RCA_CLASSIFIER = XGBoostRCAClassifier.load()
RCA_PREDICTOR = RCA_CLASSIFIER
XGBoostRCAPredictor = XGBoostRCAClassifier
