"""PortalPulse Real-time Event Streaming Routes.

Exposes:
- GET /api/v1/stream/events (W3C Standard Server-Sent Events stream)
- GET /api/v1/stream/status (Streaming health, active subscribers, buffer telemetry)
- Common aliases for backwards and cross-framework compatibility
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Header, Query, Request
from fastapi.responses import StreamingResponse

from backend.streaming.broadcaster import STREAM_BROADCASTER

logger = logging.getLogger("portalpulse.streaming.routes")

router = APIRouter(prefix="/api/v1/stream", tags=["Streaming"])
alias_router = APIRouter(tags=["Streaming Aliases"])


@router.get("/events", response_class=StreamingResponse)
async def stream_events(
    request: Request,
    last_event_id_hdr: Optional[str] = Header(None, alias="Last-Event-ID"),
    last_event_id_query: Optional[int] = Query(None, alias="last_event_id"),
) -> StreamingResponse:
    """Server-Sent Events (SSE) stream for PortalPulse real-time telemetry and control plane.

    Publishes structured events for:
    - telemetry
    - traffic
    - control_cycle
    - forecast
    - anomaly
    - rca
    - action
    - safety
    - actuation
    - warning
    - recovery
    - transaction
    - system_state
    """
    last_id: Optional[int] = None
    if last_event_id_query is not None:
        last_id = last_event_id_query
    elif last_event_id_hdr is not None:
        try:
            last_id = int(last_event_id_hdr)
        except ValueError:
            pass

    headers = {
        "Content-Type": "text/event-stream; charset=utf-8",
        "Cache-Control": "no-cache, no-transform",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }

    return StreamingResponse(
        STREAM_BROADCASTER.sse_generator(last_event_id=last_id),
        media_type="text/event-stream",
        headers=headers,
    )


@router.get("/status")
def get_stream_status() -> Dict[str, Any]:
    """Return status and subscriber telemetry for the streaming engine."""
    return {
        "status": "ONLINE",
        "streaming": STREAM_BROADCASTER.get_stats(),
    }


# ---------------------------------------------------------------------------
# ALIASES FOR EXTENSIBILITY AND DIRECT ACCESSIBILITY
# ---------------------------------------------------------------------------
@alias_router.get("/api/stream/events", response_class=StreamingResponse)
@alias_router.get("/stream/events", response_class=StreamingResponse)
async def stream_events_alias(
    request: Request,
    last_event_id_hdr: Optional[str] = Header(None, alias="Last-Event-ID"),
    last_event_id_query: Optional[int] = Query(None, alias="last_event_id"),
) -> StreamingResponse:
    return await stream_events(
        request=request,
        last_event_id_hdr=last_event_id_hdr,
        last_event_id_query=last_event_id_query,
    )


@alias_router.get("/api/stream/status")
@alias_router.get("/stream/status")
def get_stream_status_alias() -> Dict[str, Any]:
    return get_stream_status()
