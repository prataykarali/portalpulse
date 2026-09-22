"""Pydantic schemas for PortalPulse Module 7: Closed-Loop Actuator & Feedback Stabilization."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from backend.m4_action_intelligence.schema import SREAction


class ActuationRequest(BaseModel):
    """Payload to trigger an SRE action through the closed-loop actuator."""

    action: SREAction
    portal_id: Optional[str] = Field(default="nirantar", description="Target portal ID for action execution")
    parameters: Dict[str, Any] = Field(default_factory=dict)
    operator_id: str = Field(default="system_autonomous_loop")
    bypass_safety: bool = Field(
        default=False, description="Explicit manual override for disaster recovery"
    )


class MetricDelta(BaseModel):
    """Before and after operational metric delta following SRE actuation."""

    metric_name: str
    before: float
    after: float
    change_percent: float


class ActuationRecord(BaseModel):
    """Immutable audit record documenting executed action and post-action metric stabilization."""

    execution_id: str
    action: SREAction
    portal_id: str = "nirantar"
    action_level: str = "LEVEL_1_SOFTWARE"
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    operator_id: str
    status: str = "SUCCESS"
    parameters: Dict[str, Any]
    metric_deltas: List[MetricDelta]
    stabilization_trajectory: List[Dict[str, Any]]
    post_action_health: str
    execution_latency_ms: float
    notes: str


class ActuationAuditLogResponse(BaseModel):
    """Audit log history of all closed-loop actions executed on the platform."""

    total_executions: int
    executions: List[ActuationRecord]
