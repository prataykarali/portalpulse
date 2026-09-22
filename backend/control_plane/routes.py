"""FastAPI HTTP Routes for PortalPulse Multi-Portal Control Plane.

Exposes endpoints for portal registration, capability and dependency discovery,
per-portal telemetry ingestion, policy action masking, action dispatch, key provisioning,
and connection health management.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Header, HTTPException, Query, status

from backend.control_plane.registry import PORTAL_REGISTRY
from backend.control_plane.baseline import BASELINE_ENGINE, PortalBaseline
from backend.control_plane.schema import (
    MaskedRecommendation,
    PortalInfo,
    PortalListResponse,
    PortalRegistrationRequest,
    PortalRegistrationResponse,
    ProvisionKeyRequest,
    ProvisionKeyResponse,
)
from portalpulse_sdk.middleware import GLOBAL_SESSION_TRACKER
from portalpulse_sdk.schema import (
    ActionCommand,
    ActionResult,
    CapacityProfile,
    PortalCapabilities,
    ResourceProfile,
    UniversalTelemetry,
)

router = APIRouter(prefix="/api/v1/portals", tags=["Multi-Portal Control Plane"])


@router.post(
    "/keys/provision",
    response_model=ProvisionKeyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Provision a long-lived API key for a portal connector",
)
def provision_api_key(request: ProvisionKeyRequest) -> ProvisionKeyResponse:
    """Provisions a cryptographically secure long-lived API key for connector authentication."""
    return PORTAL_REGISTRY.provision_api_key(request)


@router.post(
    "/register",
    response_model=PortalRegistrationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a host portal, discover its capabilities, and compute its action mask",
)
def register_portal(
    request: PortalRegistrationRequest,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
) -> PortalRegistrationResponse:
    """Authenticates connector, indexes infrastructure capabilities, and builds dynamic DAG."""
    key = request.api_key or x_api_key
    if key and not PORTAL_REGISTRY.verify_api_key(request.portal_id, key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid API key provided for portal '{request.portal_id}'.",
        )
    return PORTAL_REGISTRY.register_portal(request)


@router.get(
    "",
    response_model=PortalListResponse,
    summary="List all registered portals and their real-time health",
)
def list_portals() -> PortalListResponse:
    """Catalog of all portals currently connected to this PortalPulse control plane."""
    return PORTAL_REGISTRY.list_portals()


@router.get(
    "/{portal_id}",
    response_model=PortalInfo,
    summary="Get detailed status and latest telemetry for a specific portal",
)
def get_portal(portal_id: str) -> PortalInfo:
    """Fetches registration metadata, latest telemetry, and status."""
    portal = PORTAL_REGISTRY.get_portal(portal_id)
    if not portal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Portal '{portal_id}' is not registered.",
        )
    return portal


@router.get(
    "/{portal_id}/capabilities",
    summary="Capability Discovery: inspect permitted infrastructure operations",
)
def get_portal_capabilities(portal_id: str) -> Dict[str, Any]:
    """Returns declared infrastructure capabilities and explicit supported/unsupported action lists."""
    portal = PORTAL_REGISTRY.get_portal(portal_id)
    if not portal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Portal '{portal_id}' is not registered.",
        )
    data = portal.capabilities.model_dump()
    data["portal_id"] = portal_id
    data["capabilities"] = portal.capabilities.model_dump()
    data["supported_actions"] = portal.supported_actions
    data["unsupported_actions"] = portal.unsupported_actions
    return data


@router.get(
    "/{portal_id}/dependencies",
    summary="Dependency Discovery: inspect dynamic topological service graph",
)
def get_portal_dependencies(portal_id: str) -> Dict[str, Any]:
    """Returns the dynamically constructed NetworkX DAG representing the portal's tiers."""
    deps = PORTAL_REGISTRY.get_dependencies(portal_id)
    if not deps:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Portal '{portal_id}' is not registered.",
        )
    return deps


@router.get(
    "/{portal_id}/resources",
    response_model=ResourceProfile,
    summary="Resource Discovery: inspect physical host, container cgroup, and process allocations",
)
def get_portal_resources(portal_id: str) -> ResourceProfile:
    """Discovers host hardware, cgroup container quotas, and configured process limits."""
    resources = PORTAL_REGISTRY.get_resources(portal_id)
    if not resources:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Resource discovery not supported or portal '{portal_id}' is not registered.",
        )
    return resources


@router.get(
    "/{portal_id}/capacity-profile",
    summary="Capacity Profile: empirical performance limits measured from capacity benchmark",
)
def get_portal_capacity_profile(portal_id: str) -> Dict[str, Any]:
    """Retrieves empirical capacity results (sustainable RPS, knee point, saturation)."""
    profile = PORTAL_REGISTRY.get_capacity_profile(portal_id)
    if not profile:
        return {
            "portal_id": portal_id,
            "status": "UNTESTED",
            "message": "Capacity profile unavailable. Run a capacity benchmark to measure empirical limits.",
            "capacity_profile": None,
        }
    return {
        "portal_id": portal_id,
        "status": "MEASURED",
        "capacity_profile": profile.model_dump(),
    }


@router.get(
    "/{portal_id}/baseline",
    response_model=PortalBaseline,
    summary="Operating Baseline: normal operating boundaries and degradation thresholds",
)
def get_portal_baseline(portal_id: str) -> PortalBaseline:
    """Computes or retrieves statistical baseline established before load testing."""
    baseline = BASELINE_ENGINE.get_baseline(portal_id)
    if not baseline:
        # Compute baseline on-demand from latest registered telemetry
        portal = PORTAL_REGISTRY.get_portal(portal_id)
        if portal and portal.latest_telemetry:
            baseline = BASELINE_ENGINE.compute_baseline_from_sample(portal_id, portal.latest_telemetry)
        else:
            conn = PORTAL_REGISTRY.get_connector(portal_id)
            if conn:
                sample = conn.get_telemetry()
                baseline = BASELINE_ENGINE.compute_baseline_from_sample(portal_id, sample)
            else:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Cannot compute baseline: portal '{portal_id}' not found.",
                )
    return baseline


@router.get(
    "/{portal_id}/sessions",
    summary="Session Analytics: active sessions, in-flight requests, and identity breakdown",
)
def get_portal_sessions(portal_id: str) -> Dict[str, Any]:
    """Inspects live active sessions (30s window), in-flight concurrent requests, and RPS."""
    p50, p95, p99 = GLOBAL_SESSION_TRACKER.get_latency_percentiles()
    return {
        "portal_id": portal_id,
        "active_sessions": GLOBAL_SESSION_TRACKER.get_active_sessions(),
        "in_flight_requests": GLOBAL_SESSION_TRACKER.get_in_flight_requests(),
        "requests_per_second": GLOBAL_SESSION_TRACKER.get_requests_per_second(),
        "p50_latency_ms": p50,
        "p95_latency_ms": p95,
        "p99_latency_ms": p99,
        "session_identity_breakdown": GLOBAL_SESSION_TRACKER.get_session_breakdown(),
    }


@router.post(
    "/{portal_id}/telemetry",
    status_code=status.HTTP_200_OK,
    summary="Ingest standardized universal telemetry from a portal connector",
)
def ingest_portal_telemetry(
    portal_id: str,
    telemetry: UniversalTelemetry,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
) -> Dict[str, Any]:
    """Receives 15-signal standardized telemetry, validates ranges, and records it in hot & historical stores."""
    if telemetry.portal_id != portal_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"URL portal_id '{portal_id}' does not match payload portal_id '{telemetry.portal_id}'.",
        )
    if x_api_key and not PORTAL_REGISTRY.verify_api_key(portal_id, x_api_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid API key for portal '{portal_id}'.",
        )
    try:
        PORTAL_REGISTRY.record_telemetry(telemetry)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Telemetry validation failed: {str(e)}",
        ) from e
    return {"status": "INGESTED", "portal_id": portal_id, "timestamp": telemetry.timestamp}


@router.post(
    "/{portal_id}/heartbeat",
    status_code=status.HTTP_200_OK,
    summary="Connector heartbeat ping to maintain active session",
)
def portal_heartbeat(portal_id: str) -> Dict[str, Any]:
    """Records a lightweight liveness pulse from an idle connector."""
    try:
        return PORTAL_REGISTRY.record_heartbeat(portal_id)
    except KeyError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e


@router.get(
    "/{portal_id}/telemetry/live",
    response_model=UniversalTelemetry,
    summary="Fetch the latest telemetry observation for a specific portal",
)
def get_live_portal_telemetry(portal_id: str) -> UniversalTelemetry:
    """Fetches the latest recorded telemetry step."""
    tel = PORTAL_REGISTRY.get_latest_telemetry(portal_id)
    if not tel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No telemetry recorded yet for portal '{portal_id}'.",
        )
    return tel


@router.get(
    "/{portal_id}/history",
    summary="Query historical telemetry time series from SQLite WAL database",
)
def get_portal_history(
    portal_id: str,
    limit: int = Query(default=100, ge=1, le=1000, description="Max historical points"),
) -> List[Dict[str, Any]]:
    """Returns time-series telemetry records for charts, drift analysis, and model training."""
    portal = PORTAL_REGISTRY.get_portal(portal_id)
    if not portal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Portal '{portal_id}' is not registered.",
        )
    return PORTAL_REGISTRY.get_telemetry_history(portal_id, limit=limit)


@router.post(
    "/watchdog",
    summary="Run watchdog heartbeat scan across all connected portals",
)
def trigger_watchdog(timeout_seconds: float = Query(default=15.0, ge=0.0, le=120.0)) -> Dict[str, Any]:
    """Marks portals with missing telemetry as TELEMETRY_LOST / DEGRADED."""
    degraded = PORTAL_REGISTRY.check_watchdog(timeout_seconds=timeout_seconds)
    return {
        "status": "WATCHDOG_CHECK_COMPLETED",
        "degraded_portals": degraded,
        "count": len(degraded),
    }


@router.post(
    "/{portal_id}/actions/prescribe-and-mask",
    response_model=MaskedRecommendation,
    summary="Evaluate M5 Action Policy and apply Portal Capability Mask",
)
def prescribe_and_mask_action(
    portal_id: str,
    telemetry: UniversalTelemetry | None = None,
) -> MaskedRecommendation:
    """Executes neural policy and filters out any unsupported actions before execution."""
    try:
        return PORTAL_REGISTRY.prescribe_and_mask_action(portal_id, telemetry)
    except KeyError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e


@router.post(
    "/{portal_id}/actions/dispatch",
    response_model=ActionResult,
    summary="Dispatch approved SRE mitigation action to host portal connector",
)
def dispatch_action(portal_id: str, command: ActionCommand) -> ActionResult:
    """Forwards action execution command to local reference connector or remote agent."""
    if command.portal_id != portal_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"URL portal_id '{portal_id}' does not match command portal_id '{command.portal_id}'.",
        )
    return PORTAL_REGISTRY.dispatch_action(portal_id, command)


@router.get(
    "/telemetry/mode",
    summary="Get current telemetry generation mode (real baseline vs simulated benchmark)",
)
def get_telemetry_mode() -> Dict[str, Any]:
    """Returns whether the connectors are emitting real idle baseline numbers or simulated stress test data."""
    is_sim = any(getattr(c, "simulation_mode", False) for c in PORTAL_REGISTRY._connectors.values())
    return {
        "simulation_mode": is_sim,
        "mode_label": "SIMULATION_BENCHMARK" if is_sim else "REAL_BASELINE",
        "description": "Simulated peak stress test" if is_sim else "Real found baseline (idle operator, 0 external users)",
    }


@router.post(
    "/telemetry/mode",
    summary="Toggle telemetry mode between real baseline and simulated benchmark",
)
def set_telemetry_mode(simulation: bool = Query(..., description="True for stress-test simulation, False for real baseline")) -> Dict[str, Any]:
    """Switches connector telemetry mode."""
    for conn in PORTAL_REGISTRY._connectors.values():
        if hasattr(conn, "simulation_mode"):
            conn.simulation_mode = simulation
    return {
        "simulation_mode": simulation,
        "mode_label": "SIMULATION_BENCHMARK" if simulation else "REAL_BASELINE",
        "status": "MODE_UPDATED",
    }


from backend.control_plane.capacity_index import CAPACITY_ENGINE, CapacityIndexReport


@router.get(
    "/{portal_id}/capacity-index",
    response_model=CapacityIndexReport,
    summary="Calculate real-time Portal Capacity Index (PCI) and multi-tier headroom",
)
def get_portal_capacity_index(portal_id: str) -> CapacityIndexReport:
    """Evaluates 5-tier physical bottlenecks (CPU, RAM, DB, Pods, SLA) and returns current PCI."""
    telemetry = PORTAL_REGISTRY.get_latest_telemetry(portal_id)
    if telemetry is None:
        conn = PORTAL_REGISTRY.get_connector(portal_id)
        if conn:
            telemetry = conn.get_telemetry()
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No telemetry found for portal '{portal_id}'",
            )
    return CAPACITY_ENGINE.compute_capacity_index(telemetry)


@router.get(
    "/capacity-index/all",
    summary="Calculate real-time Portal Capacity Index across all registered portals",
)
def get_all_capacity_indices() -> Dict[str, Any]:
    """Returns PCI and headroom reports for all active portals."""
    reports = {}
    for pid in PORTAL_REGISTRY.list_portals():
        try:
            reports[pid] = get_portal_capacity_index(pid).model_dump()
        except Exception:
            pass
    return {"reports": reports}


from backend.control_plane.portal_anatomy import get_portal_anatomy, PortalAnatomy
from backend.control_plane.avatar_engine import get_portal_avatars, PortalAvatarRoster
from backend.control_plane.health_scoring import compute_portal_health_score, compute_user_impact
from backend.control_plane.incident_timeline import TIMELINE_MANAGER
from backend.control_plane.explainable_pipeline import EXPLAINABLE_PIPELINE, PipelineExecutionCycle, CapacityCertificate


@router.get(
    "/{portal_id}/anatomy",
    response_model=PortalAnatomy,
    summary="Retrieve dynamic architecture DAG and bottleneck analysis (PRD-03 §9)",
)
def get_portal_anatomy_endpoint(portal_id: str) -> PortalAnatomy:
    """Returns 'HOW THIS PORTAL WORKS' structural DAG for Nirantar (Microservices) or IEMCRP (Monolith)."""
    return get_portal_anatomy(portal_id)


@router.get(
    "/{portal_id}/avatars",
    response_model=PortalAvatarRoster,
    summary="Retrieve state-reactive observability avatars (PRD-03 §10, §11)",
)
def get_portal_avatars_endpoint(portal_id: str) -> PortalAvatarRoster:
    """Returns 7 pipeline avatars for Nirantar or 3 domain workflow avatars for IEMCRP."""
    telemetry = PORTAL_REGISTRY.get_latest_telemetry(portal_id)
    tel_dict = telemetry.model_dump() if telemetry else None
    return get_portal_avatars(portal_id=portal_id, telemetry=tel_dict)


@router.get(
    "/{portal_id}/health-score",
    summary="Continuous 0-100 Portal Health Score and User Impact (PRD-03 §2)",
)
def get_portal_health_score_endpoint(portal_id: str) -> Dict[str, Any]:
    """Calculates continuous health composite (0-100) and human user impact metrics."""
    telemetry = PORTAL_REGISTRY.get_latest_telemetry(portal_id)
    if not telemetry:
        conn = PORTAL_REGISTRY.get_connector(portal_id)
        if conn:
            telemetry = conn.get_telemetry()
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No telemetry found for portal '{portal_id}'",
            )
    health = compute_portal_health_score(telemetry)
    user_impact = compute_user_impact(telemetry)
    return {
        "portal_id": portal_id,
        "health": health,
        "user_impact": user_impact,
    }


@router.get(
    "/{portal_id}/capacity-certificate",
    response_model=CapacityCertificate,
    summary="Official Capacity Certificate report (PRD-02 §6, PRD-03 §4)",
)
def get_capacity_certificate_endpoint(portal_id: str) -> CapacityCertificate:
    """Fetches persistent official Capacity Certificate showing sustainable RPS, knee point, and compliance."""
    if portal_id in EXPLAINABLE_PIPELINE.certificates:
        return EXPLAINABLE_PIPELINE.certificates[portal_id]
    return EXPLAINABLE_PIPELINE.generate_capacity_certificate(portal_id)


@router.get(
    "/pipeline/timeline",
    summary="Live Unified Decision Incident Timeline (PRD-03 §8)",
)
def get_incident_timeline_endpoint(
    portal_id: Optional[str] = Query(None, description="Optional portal filter"),
    limit: int = Query(50, ge=1, le=200),
) -> Dict[str, Any]:
    """Returns unified chronological event log tracing M1->M2->M3->M4->M5->M6->M7->Verify."""
    events = TIMELINE_MANAGER.get_events(portal_id=portal_id, limit=limit)
    return {
        "total_events": len(events),
        "events": [e.model_dump() for e in events],
    }


@router.get(
    "/pipeline/explainable/latest",
    summary="Latest explainable SRE cycle with model inputs, outputs, consensus, and rollback status",
)
def get_latest_explainable_cycle_endpoint(portal_id: str = Query("nirantar")) -> Dict[str, Any]:
    """Retrieves the latest execution cycle proving model execution ms, consensus, and rollback state."""
    if not EXPLAINABLE_PIPELINE.last_cycle:
        EXPLAINABLE_PIPELINE.run_cycle(portal_id=portal_id)
    return EXPLAINABLE_PIPELINE.last_cycle.model_dump()


@router.post(
    "/pipeline/explainable/execute",
    summary="Trigger an on-demand explainable SRE intelligence cycle",
)
def execute_explainable_cycle_endpoint(portal_id: str = Query("nirantar")) -> Dict[str, Any]:
    """Runs a full M1-M7 cycle with safety check, actuation, and closed-loop verification."""
    cycle = EXPLAINABLE_PIPELINE.run_cycle(portal_id=portal_id)
    return cycle.model_dump()


