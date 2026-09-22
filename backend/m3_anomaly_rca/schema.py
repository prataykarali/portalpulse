"""PortalPulse Module 3 & 4: Anomaly Detection and Root Cause Analysis Schemas.

Pydantic schemas for Isolation Forest anomaly scoring, XGBoost multi-class RCA,
and NetworkX topological dependency causal tracing.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class FailureCategory(str, Enum):
    """SRE incident root-cause failure categories."""

    NORMAL = "NORMAL"
    TRAFFIC_SPIKE = "TRAFFIC_SPIKE"
    API_CPU = "API_CPU"
    DATABASE = "DATABASE"
    NETWORK = "NETWORK"
    MEMORY = "MEMORY"
    QUEUE_OVERLOAD = "QUEUE_OVERLOAD"
    DEPENDENCY_FAILURE = "DEPENDENCY_FAILURE"


class AnomalySeverity(str, Enum):
    """Severity classification for detected anomalies."""

    NOMINAL = "NOMINAL"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class AnomalyResult(BaseModel):
    """Unsupervised Isolation Forest anomaly detection evaluation."""

    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 UTC timestamp of anomaly detection",
    )
    is_anomaly: bool = Field(..., description="True if anomaly threshold tripped")
    anomaly_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Normalized continuous anomaly score (0=nominal, 1=severe anomaly)",
    )
    raw_decision_score: float = Field(..., description="Raw Isolation Forest decision function output")
    severity: str = Field(..., description="Operating severity: NOMINAL, WARNING, or CRITICAL")
    contributing_metrics: List[Dict[str, Any]] = Field(
        default_factory=list, description="Top anomalous metrics deviating from baseline"
    )
    inference_time_ms: float = Field(..., ge=0.0, description="Detection latency in milliseconds")


class RCAResult(BaseModel):
    """Consolidated Root Cause Analysis attributing fault category and topological tier."""

    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 UTC timestamp of RCA evaluation",
    )
    primary_root_cause: FailureCategory = Field(..., description="Identified root cause failure category")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Classification confidence probability")
    probabilities: Dict[str, float] = Field(
        ..., description="Probability distribution across all 8 failure categories"
    )
    root_cause_tier: str = Field(..., description="Architectural tier identified as primary origin")
    causal_propagation_chain: List[str] = Field(
        default_factory=list,
        description="Topological propagation path (e.g. ['postgresql_db', 'worker_backend', 'api_gateway'])",
    )
    graph_propagation_confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Topological propagation confidence from NetworkX"
    )
    inference_time_ms: float = Field(..., ge=0.0, description="RCA inference latency in milliseconds")
    recommended_mitigation: str = Field(..., description="SRE tactical remediation playbook recommendation")


class TopologyNode(BaseModel):
    """Node definition for frontend dependency graph visualization."""

    id: str
    label: str
    tier: str
    status: str
    anomaly_score: float = 0.0
    metrics: Dict[str, float] = Field(default_factory=dict)


class TopologyEdge(BaseModel):
    """Directed dependency link between architectural nodes."""

    source: str
    target: str
    relation: str


class TopologyGraphResponse(BaseModel):
    """Full architectural dependency graph and live node health states."""

    nodes: List[TopologyNode]
    edges: List[TopologyEdge]
    active_anomaly_nodes: List[str] = Field(default_factory=list)
    root_cause_node: Optional[str] = None
    propagation_path: List[str] = Field(default_factory=list)
    system_health: str = "HEALTHY"


class RCADiagnoseRequest(BaseModel):
    """Custom request payload for on-demand anomaly & RCA diagnosis."""

    cpu_percent: float = Field(..., ge=0.0, le=100.0, description="CPU utilization (%)")
    ram_percent: float = Field(..., ge=0.0, le=100.0, description="RAM utilization (%)")
    requests_per_sec: float = Field(..., ge=0.0, description="Arrival rate (RPS)")
    response_time: float = Field(..., ge=0.0, description="Round-trip response time (ms)")
    error_rate: float = Field(..., ge=0.0, le=1.0, description="HTTP error rate (4xx/5xx)")
    db_latency: float = Field(..., ge=0.0, description="Database latency (ms)")
    db_connections: float = Field(..., ge=0.0, le=100.0, description="DB connection pool saturation (%)")
    queue_length: float = Field(default=0.0, ge=0.0, description="Ingress queue backlog")
    node_metrics: Optional[Dict[str, Dict[str, float]]] = Field(
        default=None, description="Optional tier-specific metric overrides"
    )
