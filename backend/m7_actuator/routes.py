"""FastAPI HTTP routes for PortalPulse Module 7: Closed-Loop Actuator & Feedback Stabilization."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from backend.m7_actuator.actuator import CLOSED_LOOP_ACTUATOR
from backend.m7_actuator.schema import (
    ActuationAuditLogResponse,
    ActuationRecord,
    ActuationRequest,
)

router = APIRouter(prefix="/api/v1/actuator", tags=["Module 7: Closed-Loop Actuator"])


@router.post(
    "/execute",
    response_model=ActuationRecord,
    summary="Execute validated SRE action and observe closed-loop platform stabilization",
)
def post_execute_action(request: ActuationRequest) -> ActuationRecord:
    """Dispatches tactical action, adjusts simulated physical metrics, and logs post-action delta."""
    try:
        return CLOSED_LOOP_ACTUATOR.execute_action(request)
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.get(
    "/audit-log",
    response_model=ActuationAuditLogResponse,
    summary="Immutable audit log of all executed actions with before/after metric deltas",
)
def get_actuation_audit_log() -> ActuationAuditLogResponse:
    """Returns execution records, parameter payloads, and stabilization trajectories."""
    return CLOSED_LOOP_ACTUATOR.get_audit_log()
