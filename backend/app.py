"""PortalPulse Main FastAPI Gateway Application.

Orchestrates all 10 modules: M1 Monitoring, M2 Prediction, M3 Anomaly,
M4 RCA, M5 Action Intelligence, M6 AI Ops Assistant, M7 Safety, and M8 Actuation.
"""

from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

ROOT_DIR = Path(__file__).resolve().parents[1]
WEBSITE_DIR = ROOT_DIR / "website"

from backend.connectors.college_portal import CollegePortalConnector
from backend.connectors.ecommerce import ECommerceConnector
from backend.connectors.gov_portal import GovPortalConnector
from backend.connectors.nirantar import NirantarConnector
from backend.control_plane.control_loop import (
    CONTROL_LOOP,
    alias_router as control_loop_alias_router,
    router as control_loop_router,
)
from backend.control_plane.registry import PORTAL_REGISTRY
from backend.control_plane.routes import router as control_plane_router
from backend.m1_monitoring.routes import router as m1_router
from backend.m2_prediction.routes import router as m2_router
from backend.m3_anomaly_rca.routes import router as m3_rca_router
from backend.m4_action_intelligence.routes import router as m4_action_router
from backend.m5_assistant.routes import router as m5_assistant_router
from backend.m6_safety_layer.routes import router as m6_safety_router
from backend.m7_actuator.routes import router as m7_actuator_router
from backend.m8_chaos_lab.routes import router as m8_chaos_router
from backend.m9_mlops_drift.routes import router as m9_mlops_router
from backend.simulation.routes import router as simulation_router
from backend.simulation.traffic_controller import (
    TRAFFIC_CONTROLLER,
    alias_router as traffic_alias_router,
    router as traffic_router,
)
from backend.streaming.broadcaster import STREAM_BROADCASTER
from backend.streaming.routes import (
    alias_router as stream_alias_router,
    router as stream_router,
)
from backend.control_plane.warning_routes import router as warning_router
from backend.control_plane.system_status import (
    alias_router as system_alias_router,
    router as system_status_router,
)
from portalpulse_sdk.middleware import PortalPulseSessionMiddleware

# Attach reference portal connectors
PORTAL_REGISTRY.attach_connector(NirantarConnector())
PORTAL_REGISTRY.attach_connector(CollegePortalConnector())
PORTAL_REGISTRY.attach_connector(ECommerceConnector())
PORTAL_REGISTRY.attach_connector(GovPortalConnector())


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Seed initial telemetry and stream live universal telemetry in background."""
    # Seed 15 historical telemetry entries for each connected portal
    for conn in list(PORTAL_REGISTRY._connectors.values()):
        for _ in range(15):
            try:
                PORTAL_REGISTRY.record_telemetry(conn.get_telemetry())
            except Exception:
                pass

    async def telemetry_loop():
        while True:
            try:
                for conn in list(PORTAL_REGISTRY._connectors.values()):
                    tel = conn.get_telemetry()
                    PORTAL_REGISTRY.record_telemetry(tel)
                    # Broadcast live telemetry via SSE
                    STREAM_BROADCASTER.publish_telemetry({
                        "type": "telemetry",
                        "timestamp": tel.timestamp or datetime.now(timezone.utc).isoformat(),
                        "portal_id": conn.portal_id,
                        "active_users": tel.active_users,
                        "requests_per_sec": tel.requests_per_sec,
                        "latency_ms": tel.latency_ms,
                        "p95_latency_ms": tel.p95_latency_ms or tel.latency_ms,
                        "cpu_percent": tel.cpu_percent,
                        "ram_percent": tel.ram_percent,
                        "db_connections": tel.db_connections,
                        "queue_length": tel.queue_length,
                        "error_rate": tel.error_rate,
                    })

                # Broadcast overall system state with live evaluated component statuses
                from backend.control_plane.system_status import evaluate_component_states
                comp_states = evaluate_component_states()
                STREAM_BROADCASTER.publish_system_state({
                    "type": "system_state",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "components": comp_states,
                    "control_loop_running": CONTROL_LOOP.running,
                    "control_loop_phase": CONTROL_LOOP.phase,
                    "current_action": CONTROL_LOOP.current_action,
                    "recovery_state": CONTROL_LOOP.recovery_state,
                    "traffic_running": TRAFFIC_CONTROLLER.is_running,
                    "traffic_phase": TRAFFIC_CONTROLLER.current_phase.value,
                    "traffic_vus": TRAFFIC_CONTROLLER.current_vus,
                    "active_subscribers": STREAM_BROADCASTER.active_subscribers_count,
                    "status": "HEALTHY",
                })
            except Exception:
                pass
            await asyncio.sleep(4.0)

    bg_task = asyncio.create_task(telemetry_loop())
    await CONTROL_LOOP.start()
    yield
    await TRAFFIC_CONTROLLER.stop()
    await CONTROL_LOOP.stop()
    await STREAM_BROADCASTER.shutdown()
    bg_task.cancel()
    try:
        await bg_task
    except asyncio.CancelledError:
        pass


app = FastAPI(
    title="PortalPulse Autonomous SRE & Control Tower API",
    version="2.0.0",
    description=(
        "Closed-loop autonomous operations platform for high-concurrency portals. "
        "Integrates telemetry ingestion, multi-horizon forecasting, anomaly detection, "
        "root cause analysis, GPU-accelerated action intelligence, deterministic safety guardrails, "
        "and a universal pluggable connector control plane."
    ),
    lifespan=lifespan,
)

# Production CORS configuration supporting here.now deployment and custom origins
allowed_origins_env = os.environ.get("ALLOWED_ORIGINS", "")
if allowed_origins_env:
    allowed_origins = [orig.strip() for orig in allowed_origins_env.split(",") if orig.strip()]
else:
    allowed_origins = [
        "https://here.now",
        "http://localhost:3000",
        "http://localhost:8000",
        "http://localhost:8501",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8000",
        "http://127.0.0.1:8501",
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=r"https://.*\.here\.now",
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
)
app.add_middleware(PortalPulseSessionMiddleware)

# Mount website static assets
if WEBSITE_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(WEBSITE_DIR)), name="static")
    if (WEBSITE_DIR / "assets").exists():
        app.mount("/assets", StaticFiles(directory=str(WEBSITE_DIR / "assets")), name="website_assets")


@app.get("/style.css")
def get_root_style():
    return FileResponse(str(WEBSITE_DIR / "style.css"))


@app.get("/app.js")
def get_root_js():
    return FileResponse(str(WEBSITE_DIR / "app.js"))

# Mount Nirantar backend API sub-application
from backend.connectors.nirantar_bridge import NIRANTAR_APP
app.mount("/portals/nirantar/api", NIRANTAR_APP)
app.mount("/nirantar/api", NIRANTAR_APP)

# Mount independent IEMCRP backend API sub-application
from backend.portals.iemcrp_app import iemcrp_app
app.mount("/portals/college/api", iemcrp_app)
app.mount("/iemcrp/api", iemcrp_app)

# Mount Nirantar's web application if present
NIRANTAR_DIST = Path(os.environ.get("NIRANTAR_DIST_DIR", str(ROOT_DIR.parent / "NIRANTAR" / "frontend" / "dist")))
if NIRANTAR_DIST.exists():
    app.mount("/portals/nirantar", StaticFiles(directory=str(NIRANTAR_DIST), html=True), name="nirantar_portal")
    if (NIRANTAR_DIST / "assets").exists():
        app.mount("/assets", StaticFiles(directory=str(NIRANTAR_DIST / "assets")), name="nirantar_assets")


# Mount interactive reference demo portals
PORTALS_DIR = WEBSITE_DIR / "portals"
if PORTALS_DIR.exists():
    app.mount("/portals/demo", StaticFiles(directory=str(PORTALS_DIR), html=True), name="demo_portals")


# Mount Modules
app.include_router(control_plane_router)
app.include_router(control_loop_router)
app.include_router(control_loop_alias_router)
app.include_router(traffic_router)
app.include_router(traffic_alias_router)
app.include_router(stream_router)
app.include_router(stream_alias_router)
app.include_router(simulation_router)
app.include_router(m1_router)
app.include_router(m2_router)
app.include_router(m3_rca_router)
app.include_router(m4_action_router)
app.include_router(m5_assistant_router)
app.include_router(m6_safety_router)
app.include_router(m7_actuator_router)
app.include_router(m8_chaos_router)
app.include_router(m9_mlops_router)
app.include_router(warning_router)
app.include_router(system_status_router)
app.include_router(system_alias_router)


@app.get("/")
def get_root(request: Request) -> Any:
    """Serves the interactive PortalPulse landing website for browsers, or API JSON status for API clients."""
    accept = request.headers.get("accept", "")
    if "text/html" in accept and (WEBSITE_DIR / "index.html").exists():
        return FileResponse(str(WEBSITE_DIR / "index.html"))

    return {
        "service": "PortalPulse Control Tower API",
        "version": "2.0.0",
        "status": "ONLINE",
        "active_modules": [
            "M1_MONITORING_INGESTION",
            "M2_PREDICTION_XGBOOST",
            "M3_ANOMALY_ISOLATION_FOREST",
            "M4_RCA_XGBOOST_NETWORKX",
            "M5_ACTION_INTELLIGENCE_MLP",
            "M6_AI_ASSISTANT_LLM_RAG",
            "M7_SAFETY_GUARDRAILS",
            "M8_ACTUATOR_EXECUTION",
            "M9_CHAOS_STRESS_LAB",
            "M10_MLOPS_DRIFT_GOVERNANCE",
        ],
        "planned_modules": [],
        "docs_url": "/docs",
        "website_url": "/website",
    }


@app.get("/website")
@app.get("/app")
@app.get("/app/{full_path:path}")
def get_website_app() -> Any:
    """Serve the PortalPulse Web Application Shell & Command Center."""
    if (WEBSITE_DIR / "index.html").exists():
        return FileResponse(str(WEBSITE_DIR / "index.html"))
    return {"status": "ONLINE", "message": "Website directory not found"}


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("backend.app:app", host="0.0.0.0", port=port, reload=False)
