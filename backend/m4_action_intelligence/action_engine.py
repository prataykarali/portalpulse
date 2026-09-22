"""Production Action Intelligence Engine for PortalPulse.

Encapsulates PyTorch deep policy model inference, input vector standardization,
softmax probability distribution extraction, domain tactical rationale generation,
blast radius safety assessment, and Human-in-the-Loop (HITL) approval flags.
"""

from __future__ import annotations

import os
import pickle
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import numpy as np
import torch

from backend.m1_monitoring.schema import DerivedFeatures, RawTelemetry
from backend.m2_prediction.schema import ForecastResult
from backend.m3_anomaly_rca.schema import RCAResult
from backend.m4_action_intelligence.policy_net import (
    ActionPolicyMLP,
    get_device,
)
from backend.m4_action_intelligence.schema import (
    ACTION_BLAST_RADIUS,
    ACTION_DESCRIPTIONS,
    ACTION_INDEX_MAP,
    STATE_FEATURE_NAMES,
    ActionRecommendation,
    ActionStateVector,
    SREAction,
)

MODELS_DIR = Path(__file__).resolve().parent / "models"
DEFAULT_CHECKPOINT_PATH = Path(os.environ.get("M5_CHECKPOINT_PATH", str(MODELS_DIR / "action_mlp_policy.pt")))
DEFAULT_SCALER_PATH = Path(os.environ.get("M5_SCALER_PATH", str(MODELS_DIR / "scaler.pkl")))


class ActionIntelligenceEngine:
    """Production SRE Prescriptive Action Policy Engine powered by Deep PyTorch MLP."""

    def __init__(
        self,
        checkpoint_path: Optional[Path] = None,
        scaler_path: Optional[Path] = None,
        device: Optional[torch.device] = None,
    ) -> None:
        self.device = device or get_device()
        self.checkpoint_path = checkpoint_path or DEFAULT_CHECKPOINT_PATH
        self.scaler_path = scaler_path or DEFAULT_SCALER_PATH
        self.model: Optional[ActionPolicyMLP] = None
        self.scaler: Optional[Any] = None
        self.metadata: Dict[str, Any] = {}
        self.feature_names = STATE_FEATURE_NAMES
        self.is_ready: bool = False

        self._load_artifacts()

    def _load_artifacts(self) -> None:
        """Load serialized PyTorch model checkpoint and StandardScaler."""
        if self.checkpoint_path.exists() and self.scaler_path.exists():
            try:
                self.model, self.metadata = ActionPolicyMLP.load_checkpoint(
                    self.checkpoint_path, map_location=self.device
                )
                with open(self.scaler_path, "rb") as f:
                    self.scaler = pickle.load(f)
                self.is_ready = True
            except Exception as e:
                print(f"[ActionIntelligenceEngine] Warning: Failed to load checkpoint: {e}")
                self._fallback_init()
        else:
            self._fallback_init()

    def _fallback_init(self) -> None:
        """Initialize lightweight fallback policy when checkpoints are absent."""
        self.model = ActionPolicyMLP(input_dim=13, output_dim=11).to(self.device)
        self.model.eval()
        self.scaler = None
        self.is_ready = True

    def extract_state_vector(
        self,
        state: Union[
            ActionStateVector,
            RawTelemetry,
            Dict[str, Any],
            List[float],
        ],
        derived: Optional[DerivedFeatures] = None,
        forecast: Optional[ForecastResult] = None,
        rca: Optional[RCAResult] = None,
    ) -> np.ndarray:
        """Extract and order the 13-dimensional input feature vector.

        Returns:
            np.ndarray of shape (1, 13) with dtype float32.
        """
        if isinstance(state, ActionStateVector):
            vec = state.to_list()

        elif isinstance(state, RawTelemetry):
            # Extract from live telemetry, forecast, and RCA objects
            fut_rps = forecast.rps_5m if forecast else float(state.requests_per_sec * 1.05)
            fut_cpu = forecast.cpu_5m if forecast else float(state.cpu_percent * 1.02)
            fut_lat = forecast.latency_5m if forecast else float(state.response_time * 1.05)
            anom = 0.85 if rca and rca.primary_root_cause.value != "NORMAL" else 0.15
            rca_conf = rca.confidence if rca else 0.20

            vec = [
                float(state.cpu_percent),
                float(state.ram_percent),
                float(state.requests_per_sec),
                float(state.response_time),
                float(state.error_rate),
                float(fut_rps),
                float(fut_cpu),
                float(fut_lat),
                float(anom),
                float(rca_conf),
                float(state.db_connections),
                float(state.queue_length),
                float(state.service_instances),
            ]

        elif isinstance(state, dict):
            vec = [
                float(state.get("cpu_percent", 35.0)),
                float(state.get("ram_percent", 42.0)),
                float(state.get("requests_per_sec", 400.0)),
                float(state.get("response_time", 65.0)),
                float(state.get("error_rate", 0.001)),
                float(state.get("future_rps_5m", state.get("requests_per_sec", 400.0) * 1.05)),
                float(state.get("future_cpu_5m", state.get("cpu_percent", 35.0) * 1.02)),
                float(state.get("future_latency_5m", state.get("response_time", 65.0) * 1.05)),
                float(state.get("anomaly_score", 0.10)),
                float(state.get("rca_confidence", 0.15)),
                float(state.get("db_connections", 25.0)),
                float(state.get("queue_length", 0.0)),
                float(state.get("service_instances", 4.0)),
            ]

        elif isinstance(state, list):
            if len(state) != len(self.feature_names):
                raise ValueError(
                    f"Expected {len(self.feature_names)} features, received {len(state)}"
                )
            vec = [float(v) for v in state]

        else:
            raise TypeError(f"Unsupported state input type: {type(state)}")

        return np.array([vec], dtype=np.float32)

    def _generate_rationale(
        self,
        action: SREAction,
        raw_vec: np.ndarray,
        confidence: float,
    ) -> str:
        """Construct domain-informed SRE diagnostic rationale for recommendation."""
        v = raw_vec[0]
        cpu, ram, rps, lat, err = v[0], v[1], v[2], v[3], v[4]
        fut_rps, fut_cpu, _fut_lat = v[5], v[6], v[7]
        _anom, _rca_c, db_conn, queue, inst = v[8], v[9], v[10], v[11], v[12]

        if action == SREAction.NO_OP:
            return (
                f"Operational metrics nominal (CPU: {cpu:.1f}%, Latency: {lat:.0f}ms, Error: {err:.3f}). "
                f"Forecast projects steady headroom over +5m. No automated intervention required."
            )
        elif action == SREAction.SCALE_OUT_WORKERS:
            return (
                f"Worker CPU utilization saturated at {cpu:.1f}% with +5m forecast climbing to {fut_cpu:.1f}%. "
                f"Current instance pool ({int(inst)} replicas) insufficient; triggering HPA horizontal scale-out."
            )
        elif action == SREAction.SCALE_IN_WORKERS:
            return (
                f"Low system utilization detected (CPU: {cpu:.1f}%, RPS: {rps:.0f}) across {int(inst)} replicas. "
                f"Safely consolidating underutilized worker pods to optimize cloud expenditure."
            )
        elif action == SREAction.ACTIVATE_RATE_LIMIT:
            return (
                f"Ingress traffic surging at {rps:.0f} RPS (+5m forecast: {fut_rps:.0f} RPS). "
                f"Activating edge token-bucket rate limiting to protect downstream services from degradation."
            )
        elif action == SREAction.INCREASE_DB_POOL:
            return (
                f"Database connection pool at {db_conn:.1f}% capacity with DB latency elevated. "
                f"Expanding connection pool ceiling and terminating idle sessions to relieve transaction queue."
            )
        elif action == SREAction.PURGE_REDIS_CACHE:
            return (
                f"Elevated cache miss-rates and latency degradation ({lat:.0f}ms) detected. "
                f"Flushing stale cache partitions and triggering proactive warm-up for hot queries."
            )
        elif action == SREAction.DRAIN_REQUEST_QUEUE:
            return (
                f"Critical queue congestion detected with {int(queue)} pending requests. "
                f"Draining low-priority background workers and shedding non-critical ingress jobs."
            )
        elif action == SREAction.ENGAGE_CIRCUIT_BREAKER:
            return (
                f"Severe HTTP 5xx error rate spike ({err * 100.0:.2f}%) indicating downstream dependency failure. "
                f"Tripping circuit breaker open and serving fallback responses to maintain core availability."
            )
        elif action == SREAction.RESTART_DEGRADED_PODS:
            return (
                f"Worker container memory saturation at {ram:.1f}% with steady leak profile. "
                f"Executing rolling restart of affected pods to reclaim unreferenced heap."
            )
        elif action == SREAction.DIVERT_READS_TO_REPLICA:
            return (
                f"Primary database contention detected (conn: {db_conn:.1f}%, lat: {lat:.0f}ms). "
                f"Diverting all analytical and read-only traffic to secondary replica nodes."
            )
        elif action == SREAction.ENABLE_WAITING_ROOM:
            return (
                f"Catastrophic flash crowd observed at {rps:.0f} RPS with queue reaching {int(queue)}. "
                f"Enabling Cloudflare dynamic waiting room queue to throttle user admission into portal."
            )

        return ACTION_DESCRIPTIONS.get(action, "Executing tactical SRE playbook.")

    def recommend(
        self,
        state: Union[
            ActionStateVector,
            RawTelemetry,
            Dict[str, Any],
            List[float],
        ],
        derived: Optional[DerivedFeatures] = None,
        forecast: Optional[ForecastResult] = None,
        rca: Optional[RCAResult] = None,
    ) -> ActionRecommendation:
        """Evaluate current system state and emit prescriptive tactical SRE recommendation.

        Args:
            state: Unified state vector or raw telemetry.
            derived: Optional rolling features.
            forecast: Optional multi-horizon prediction.
            rca: Optional diagnostic root cause analysis.

        Returns:
            ActionRecommendation with primary action, confidence, blast radius,
            HITL approval requirement, and tactical rationale.
        """
        start_time = time.perf_counter()
        raw_vec = self.extract_state_vector(state, derived=derived, forecast=forecast, rca=rca)

        # Apply StandardScaler if available
        if self.scaler is not None:
            norm_vec = self.scaler.transform(raw_vec).astype(np.float32)
        else:
            norm_vec = raw_vec

        tensor_x = torch.from_numpy(norm_vec).to(self.device)

        if self.model is None:
            raise RuntimeError("ActionPolicyMLP model is not initialized.")

        # Compute softmax action probabilities
        with torch.no_grad():
            probs = self.model.predict_proba(tensor_x)[0].cpu().numpy()

        pred_idx = int(np.argmax(probs))
        confidence = float(probs[pred_idx])
        primary_action = ACTION_INDEX_MAP[pred_idx]

        # Build full probability dictionary
        all_probs: Dict[str, float] = {}
        for idx, act in ACTION_INDEX_MAP.items():
            all_probs[act.value] = round(float(probs[idx]), 4)

        # Determine blast radius and Human-in-the-Loop (HITL) requirements
        blast_radius = ACTION_BLAST_RADIUS.get(primary_action, "LOW")

        # Per secure_action.md:
        # Requires human approval if:
        # 1. Softmax confidence < 80% (0.80)
        # 2. Blast radius is HIGH (DRAIN_REQUEST_QUEUE, ENGAGE_CIRCUIT_BREAKER, RESTART_DEGRADED_PODS)
        # 3. Non-nominal action when system has active uncertainty
        requires_approval = (
            (primary_action != SREAction.NO_OP)
            and (confidence < 0.80 or blast_radius == "HIGH")
        )

        rationale = self._generate_rationale(primary_action, raw_vec, confidence)
        inference_time_ms = round((time.perf_counter() - start_time) * 1000.0, 3)

        return ActionRecommendation(
            primary_action=primary_action,
            action_id=pred_idx,
            confidence=round(confidence, 4),
            all_action_probabilities=all_probs,
            tactical_rationale=rationale,
            estimated_blast_radius=blast_radius,
            requires_human_approval=requires_approval,
            inference_time_ms=inference_time_ms,
        )

    def reload(self) -> None:
        """Reload models and scalers from disk."""
        self._load_artifacts()


# Global production engine singleton
ACTION_ENGINE = ActionIntelligenceEngine()
