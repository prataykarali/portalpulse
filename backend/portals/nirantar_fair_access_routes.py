"""Prototype Fair Access Guard API. Not connected to real railway systems."""

from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.portals.nirantar_fair_access_layer import get_fair_access_layer

router = APIRouter(prefix="/api/v1/fair-access", tags=["Fair Access"])


class AdmitRequest(BaseModel):
    action: str = "SEARCH_TRAINS"
    session_id: str = "anon"
    origin: Optional[str] = None
    destination: Optional[str] = None
    travel_date: Optional[str] = None
    journey_id: Optional[str] = None


class SimulateRequest(BaseModel):
    demand_level: str = Field(..., description="NORMAL | ELEVATED | HIGH | SURGE")


@router.post("/admit")
def admit_request(payload: AdmitRequest) -> Dict[str, Any]:
    layer = get_fair_access_layer()
    ticket = layer.admit(
        action=payload.action,
        session_id=payload.session_id,
        origin=payload.origin,
        destination=payload.destination,
        travel_date=payload.travel_date,
        journey_id=payload.journey_id,
    )
    return {"status": 200, **ticket}


@router.get("/status/{ticket_id}")
def get_ticket_status(ticket_id: str) -> Dict[str, Any]:
    ticket = get_fair_access_layer().status(ticket_id)
    if not ticket:
        raise HTTPException(404, "Fair-access ticket not found")
    return {"status": 200, **ticket}


@router.get("/snapshot")
def snapshot() -> Dict[str, Any]:
    return {"status": 200, **get_fair_access_layer().snapshot()}


@router.post("/simulate")
def simulate_demand(payload: SimulateRequest) -> Dict[str, Any]:
    return {"status": 200, **get_fair_access_layer().set_demand_level(payload.demand_level)}
