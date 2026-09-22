"""Pydantic schemas for PortalPulse Module 6: Deterministic Safety Layer & HITL Gate.

Enforces zero-ML deterministic safety guardrails, token bucket rate limiting,
circuit breakers, 5-minute flapping cooldowns, and 2-phase human-in-the-loop approvals.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from backend.m4_action_intelligence.schema import SREAction


class ApprovalStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    AUTO_EXECUTED = "AUTO_EXECUTED"


class CircuitState(str, Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class ActionIntent(BaseModel):
    """Proposed SRE action submitted for deterministic safety validation."""

    action: SREAction
    confidence: float = Field(..., ge=0.0, le=1.0, description="Model confidence score")
    requested_by: str = Field(default="policy_network", description="Originating module or agent")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Action execution parameters")
    justification: str = Field(default="", description="Technical rationale from AI policy")


class SafetyValidationResult(BaseModel):
    """Decision emitted by the deterministic safety rules engine."""

    is_safe: bool = Field(..., description="True if action passes all deterministic guardrails")
    requires_human_approval: bool = Field(
        ..., description="True if action requires operator confirmation prior to actuation"
    )
    rejection_reasons: List[str] = Field(default_factory=list, description="List of violated safety rules")
    blast_radius: str = Field(..., description="Blast radius tier: NONE, LOW, MEDIUM, HIGH")
    cooldown_remaining_sec: float = Field(default=0.0, description="Remaining seconds in action cooldown")
    approval_request_id: Optional[str] = Field(
        default=None, description="Generated request ID if human sign-off is required"
    )
    circuit_state: CircuitState = Field(default=CircuitState.CLOSED)
    rate_limit_available: bool = Field(default=True)


class ApprovalRequest(BaseModel):
    """Pending action awaiting operator human-in-the-loop confirmation."""

    request_id: str
    action: SREAction
    confidence: float
    blast_radius: str
    justification: str
    parameters: Dict[str, Any]
    requested_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    expires_at: str
    status: ApprovalStatus = ApprovalStatus.PENDING
    operator_id: Optional[str] = None
    decision_comment: Optional[str] = None
    decided_at: Optional[str] = None


class ApprovalDecisionRequest(BaseModel):
    """Operator submission approving or rejecting a pending SRE action."""

    request_id: str
    approved: bool
    operator_id: str = Field(default="sre_oncall_lead")
    comment: str = Field(default="Approved pursuant to operational runbook review.")


class ApprovalDecisionResponse(BaseModel):
    """Response acknowledging operator decision and actuation status."""

    request_id: str
    status: ApprovalStatus
    message: str
    operator_id: str
    decided_at: str


class PendingApprovalsResponse(BaseModel):
    """List of all actions awaiting operator approval."""

    total_pending: int
    requests: List[ApprovalRequest]


class CircuitBreakerStatusResponse(BaseModel):
    """Status payload for edge circuit breaker and token bucket rate limiter."""

    state: CircuitState
    failure_count: int
    failure_threshold: int
    error_rate_window: float
    recovery_timeout_sec: float
    token_bucket_available: float
    token_bucket_capacity: float
    token_bucket_refill_rate: float
