"""Pydantic schemas and action definitions for PortalPulse Module 4: Action Intelligence.

Codifies the 11 discrete tactical SRE mitigation actions defined in secure_action.md,
the 13-dimensional unified system state vector, and the typed action recommendation outputs.
"""

from __future__ import annotations

from enum import Enum
from typing import Dict, List

from pydantic import BaseModel, Field


class SREAction(str, Enum):
    """Discrete tactical SRE actions supported by the autonomous control tower."""

    NO_OP = "NO_OP"
    SCALE_OUT_WORKERS = "SCALE_OUT_WORKERS"
    SCALE_IN_WORKERS = "SCALE_IN_WORKERS"
    ACTIVATE_RATE_LIMIT = "ACTIVATE_RATE_LIMIT"
    INCREASE_DB_POOL = "INCREASE_DB_POOL"
    PURGE_REDIS_CACHE = "PURGE_REDIS_CACHE"
    DRAIN_REQUEST_QUEUE = "DRAIN_REQUEST_QUEUE"
    ENGAGE_CIRCUIT_BREAKER = "ENGAGE_CIRCUIT_BREAKER"
    RESTART_DEGRADED_PODS = "RESTART_DEGRADED_PODS"
    DIVERT_READS_TO_REPLICA = "DIVERT_READS_TO_REPLICA"
    ENABLE_WAITING_ROOM = "ENABLE_WAITING_ROOM"


ACTION_INDEX_MAP: Dict[int, SREAction] = {
    0: SREAction.NO_OP,
    1: SREAction.SCALE_OUT_WORKERS,
    2: SREAction.SCALE_IN_WORKERS,
    3: SREAction.ACTIVATE_RATE_LIMIT,
    4: SREAction.INCREASE_DB_POOL,
    5: SREAction.PURGE_REDIS_CACHE,
    6: SREAction.DRAIN_REQUEST_QUEUE,
    7: SREAction.ENGAGE_CIRCUIT_BREAKER,
    8: SREAction.RESTART_DEGRADED_PODS,
    9: SREAction.DIVERT_READS_TO_REPLICA,
    10: SREAction.ENABLE_WAITING_ROOM,
}

ACTION_NAME_TO_INDEX: Dict[SREAction, int] = {v: k for k, v in ACTION_INDEX_MAP.items()}

ACTION_BLAST_RADIUS: Dict[SREAction, str] = {
    SREAction.NO_OP: "NONE",
    SREAction.SCALE_OUT_WORKERS: "LOW",
    SREAction.SCALE_IN_WORKERS: "LOW",
    SREAction.ACTIVATE_RATE_LIMIT: "MEDIUM",
    SREAction.INCREASE_DB_POOL: "MEDIUM",
    SREAction.PURGE_REDIS_CACHE: "LOW",
    SREAction.DRAIN_REQUEST_QUEUE: "HIGH",
    SREAction.ENGAGE_CIRCUIT_BREAKER: "HIGH",
    SREAction.RESTART_DEGRADED_PODS: "HIGH",
    SREAction.DIVERT_READS_TO_REPLICA: "MEDIUM",
    SREAction.ENABLE_WAITING_ROOM: "MEDIUM",
}

ACTION_DESCRIPTIONS: Dict[SREAction, str] = {
    SREAction.NO_OP: "System operational parameters nominal. Continue continuous telemetry polling.",
    SREAction.SCALE_OUT_WORKERS: "Add backend worker replicas horizontally via Kubernetes HPA to handle compute surge.",
    SREAction.SCALE_IN_WORKERS: "Consolidate underutilized worker pods during low traffic to minimize cloud spend.",
    SREAction.ACTIVATE_RATE_LIMIT: "Engage edge token-bucket rate limiting at CDN/Ingress layer to throttle excessive requests.",
    SREAction.INCREASE_DB_POOL: "Expand PostgreSQL connection pool ceiling and recycle idle connections under pool exhaustion.",
    SREAction.PURGE_REDIS_CACHE: "Flush stale/polluted Redis cache keys and trigger lazy re-population for hot queries.",
    SREAction.DRAIN_REQUEST_QUEUE: "Apply load shedding to drop low-priority asynchronous jobs and relieve worker queue buffer.",
    SREAction.ENGAGE_CIRCUIT_BREAKER: "Trip open circuit breaker on failing upstream dependency to prevent cascading thread starvation.",
    SREAction.RESTART_DEGRADED_PODS: "Execute rolling restart of worker pods exhibiting memory leak or zombie process degradation.",
    SREAction.DIVERT_READS_TO_REPLICA: "Redirect all non-mutating SQL read queries to read-replicas to relieve primary DB lock congestion.",
    SREAction.ENABLE_WAITING_ROOM: "Divert excess incoming users to a Cloudflare dynamic FIFO virtual waiting room queue.",
}

# 13 Unified Input Features for Action Policy
STATE_FEATURE_NAMES: List[str] = [
    "cpu_percent",
    "ram_percent",
    "requests_per_sec",
    "response_time",
    "error_rate",
    "future_rps_5m",
    "future_cpu_5m",
    "future_latency_5m",
    "anomaly_score",
    "rca_confidence",
    "db_connections",
    "queue_length",
    "service_instances",
]


class ActionStateVector(BaseModel):
    """Unified 13-dimensional input state vector combining telemetry, forecast, and diagnostic signals."""

    cpu_percent: float = Field(..., ge=0.0, le=100.0, description="Current CPU utilization (%)")
    ram_percent: float = Field(..., ge=0.0, le=100.0, description="Current RAM utilization (%)")
    requests_per_sec: float = Field(..., ge=0.0, description="Observed ingress RPS")
    response_time: float = Field(..., ge=0.0, description="p95 response latency (ms)")
    error_rate: float = Field(..., ge=0.0, le=1.0, description="HTTP 5xx error fraction [0.0, 1.0]")
    future_rps_5m: float = Field(..., ge=0.0, description="M2 Forecasted RPS at +5 minutes")
    future_cpu_5m: float = Field(..., ge=0.0, le=100.0, description="M2 Forecasted CPU (%) at +5 minutes")
    future_latency_5m: float = Field(..., ge=0.0, description="M2 Forecasted Latency (ms) at +5 minutes")
    anomaly_score: float = Field(..., ge=0.0, le=1.0, description="M3 Isolation Forest anomaly score [0.0, 1.0]")
    rca_confidence: float = Field(..., ge=0.0, le=1.0, description="M4 RCA attribution confidence score [0.0, 1.0]")
    db_connections: float = Field(..., ge=0.0, description="Active database connection pool utilization (%)")
    queue_length: float = Field(..., ge=0.0, description="Pending requests in ingress buffer")
    service_instances: float = Field(..., ge=1.0, description="Current active worker replicas")

    def to_list(self) -> List[float]:
        """Convert state fields to an ordered list of floats matching STATE_FEATURE_NAMES."""
        return [
            float(self.cpu_percent),
            float(self.ram_percent),
            float(self.requests_per_sec),
            float(self.response_time),
            float(self.error_rate),
            float(self.future_rps_5m),
            float(self.future_cpu_5m),
            float(self.future_latency_5m),
            float(self.anomaly_score),
            float(self.rca_confidence),
            float(self.db_connections),
            float(self.queue_length),
            float(self.service_instances),
        ]


class ActionRecommendation(BaseModel):
    """Prescriptive recommendation emitted by the Action Intelligence Deep Policy Network."""

    primary_action: SREAction = Field(..., description="Highest-scoring tactical SRE action")
    action_id: int = Field(..., description="Action index [0-10]")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Softmax confidence score for primary action")
    all_action_probabilities: Dict[str, float] = Field(
        ..., description="Normalized softmax distribution across all 11 tactical actions"
    )
    tactical_rationale: str = Field(..., description="Plain-English explanation of why this action was chosen")
    estimated_blast_radius: str = Field(..., description="Blast radius assessment: NONE, LOW, MEDIUM, HIGH")
    requires_human_approval: bool = Field(
        ..., description="Enforces HITL review if confidence < 80% or HIGH blast radius"
    )
    inference_time_ms: float = Field(..., description="Per-sample PyTorch forward-pass latency in ms")


class ActionDefinition(BaseModel):
    """Specification of an SRE action in the control tower catalog."""

    action_id: int
    action_name: str
    description: str
    blast_radius: str
    requires_approval_by_default: bool


class ActionCatalogResponse(BaseModel):
    """API response listing all available actions in the tactical catalog."""

    total_actions: int
    actions: List[ActionDefinition]


class ActionMetadataResponse(BaseModel):
    """API response summarizing model architecture, accuracy benchmarks, and hardware target."""

    model_architecture: str
    device: str
    parameters_count: int
    test_accuracy: float
    p95_latency_ms: float
    features: List[str]
    actions_count: int
