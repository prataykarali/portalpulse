"""FastAPI HTTP routes for PortalPulse Module 6: Deterministic Safety Layer & HITL Gate."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from backend.m6_safety_layer.guardrails import SAFETY_GUARDRAILS
from backend.m6_safety_layer.schema import (
    ActionIntent,
    ApprovalDecisionRequest,
    ApprovalDecisionResponse,
    CircuitBreakerStatusResponse,
    PendingApprovalsResponse,
    SafetyValidationResult,
)

router = APIRouter(prefix="/api/v1/safety", tags=["Module 6: Safety Layer & HITL Gate"])


@router.post(
    "/validate",
    response_model=SafetyValidationResult,
    summary="Validate proposed SRE action against zero-ML deterministic guardrails",
)
def post_validate_action(intent: ActionIntent) -> SafetyValidationResult:
    """Evaluates minimum confidence (>=80%), flapping cooldowns, blast radius, and resource limits."""
    return SAFETY_GUARDRAILS.validate_action(intent)


@router.get(
    "/approvals/pending",
    response_model=PendingApprovalsResponse,
    summary="List all SRE actions currently awaiting Human-in-the-Loop operator sign-off",
)
def get_pending_approvals() -> PendingApprovalsResponse:
    """Returns pending actions that breached confidence thresholds or high blast-radius rules."""
    reqs = SAFETY_GUARDRAILS.get_pending_approvals()
    return PendingApprovalsResponse(total_pending=len(reqs), requests=reqs)


@router.post(
    "/approvals/decide",
    response_model=ApprovalDecisionResponse,
    summary="Operator decision (approve or reject) on a pending SRE action",
)
def post_decide_approval(decision: ApprovalDecisionRequest) -> ApprovalDecisionResponse:
    """Records human operator approval/rejection and updates audit status."""
    try:
        return SAFETY_GUARDRAILS.decide_approval(
            request_id=decision.request_id,
            approved=decision.approved,
            operator_id=decision.operator_id,
            comment=decision.comment,
        )
    except KeyError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


@router.get(
    "/circuit-breaker",
    response_model=CircuitBreakerStatusResponse,
    summary="Inspect state of edge circuit breaker and token bucket rate limiter",
)
def get_circuit_breaker_status() -> CircuitBreakerStatusResponse:
    """Returns circuit breaker state (CLOSED/OPEN/HALF_OPEN) and token bucket capacity."""
    return SAFETY_GUARDRAILS.get_circuit_breaker_status()
