"""API routes for Module 8: Warnings Engine."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.control_plane.warning_engine import WARNING_ENGINE, WARNING_SPECS
from backend.streaming.broadcaster import STREAM_BROADCASTER

router = APIRouter(prefix="/api/v1/warnings", tags=["Warnings Engine"])


class TestWarningRequest(BaseModel):
    warning_id: str = Field(..., description="Warning identifier to simulate (e.g. WARN_DB_POOL_EXHAUSTION)")


@router.get("/active")
def get_active_warnings() -> List[Dict[str, Any]]:
    """Return all currently active telemetry-triggered warnings."""
    return WARNING_ENGINE.get_active_warnings()


@router.get("/catalog")
def get_warnings_catalog() -> Dict[str, Any]:
    """Return catalog of all 6 canonical PortalPulse warnings and their thresholds."""
    return WARNING_ENGINE.get_catalog()


@router.post("/trigger-test")
def trigger_test_warning(req: TestWarningRequest) -> Dict[str, Any]:
    """Developer/demo trigger strictly marked as [TEST MODE]. Broadcasts over SSE."""
    try:
        item = WARNING_ENGINE.trigger_test_scenario(req.warning_id)
        item_dict = item.to_dict()
        # Broadcast via SSE
        STREAM_BROADCASTER.publish_warning(item_dict)
        return {"status": "TRIGGERED", "mode": "TEST MODE", "warning": item_dict}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
