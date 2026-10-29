"""Local IEMCRP demonstration controls; all displayed model results come from real cycles."""

from __future__ import annotations

import os
from typing import Any

from fastapi import APIRouter, HTTPException

from backend.control_plane.control_loop import CONTROL_LOOP
from backend.control_plane.warning_engine import WARNING_ENGINE
from backend.m2_prediction.forecaster import FORECASTER
from backend.m3_anomaly_rca.anomaly_detector import DETECTOR
from backend.m3_anomaly_rca.dependency_graph import TOPOLOGY_DAG
from backend.m3_anomaly_rca.rca_classifier import RCA_CLASSIFIER
from backend.m4_action_intelligence.action_engine import ACTION_ENGINE
from backend.m4_action_intelligence.schema import STATE_FEATURE_NAMES
from backend.m6_safety_layer.guardrails import SAFETY_GUARDRAILS
from backend.portals.iemcrp_app import DB_POOL, IEMCRP_INFRA_STATE
from backend.simulation.traffic_controller import (
    DEMO_START_TEMPERATURE_C,
    TRAFFIC_CONTROLLER,
    TrafficPhase,
    cpu_package_temperature_c,
)
from backend.simulation.nirantar_simulation import NIRANTAR_SIMULATION
from backend.streaming.broadcaster import STREAM_BROADCASTER

router = APIRouter(prefix="/api/v1/live-demo", tags=["Local live demonstration"])


def _require_demo() -> None:
    if os.getenv("PORTALPULSE_DEMO_MODE") != "1":
        raise HTTPException(403, "Local demo mode is disabled")


@router.get("/snapshot")
def snapshot() -> dict[str, Any]:
    _require_demo()
    college_cycles = [cycle for cycle in CONTROL_LOOP.history if cycle.portal_id == "college_portal"]
    model = ACTION_ENGINE.model
    layers = (
        []
        if model is None
        else [
            model.fc1.in_features,
            model.fc1.out_features,
            model.fc2.out_features,
            model.fc3.out_features,
            model.fc4.out_features,
            model.out_head.out_features,
        ]
    )
    return {
        "nirantar_url": os.getenv("NIRANTAR_DEMO_URL", "https://bronze-tinsel-n8pb.here.now/"),
        "traffic": TRAFFIC_CONTROLLER.get_status().model_dump(),
        "transactions": [x.model_dump() for x in TRAFFIC_CONTROLLER.get_recent_transactions(12)],
        "pool": DB_POOL.get_stats(),
        "infrastructure": dict(IEMCRP_INFRA_STATE),
        "loop": CONTROL_LOOP.get_status().model_dump(),
        "latest": college_cycles[-1].model_dump() if college_cycles else None,
        "history": [cycle.model_dump() for cycle in college_cycles[-10:]],
        "models": {
            "m2_loaded": FORECASTER.model is not None,
            "m3_loaded": DETECTOR.is_ready,
            "m3_threshold": DETECTOR.threshold,
            "m4_loaded": RCA_CLASSIFIER.is_ready,
            "m5_loaded": ACTION_ENGINE.checkpoint_path.exists()
            and ACTION_ENGINE.scaler_path.exists()
            and ACTION_ENGINE.is_ready,
            "m5_layers": layers,
            "m5_features": STATE_FEATURE_NAMES,
            "topology_nodes": list(TOPOLOGY_DAG.traffic_dag.nodes),
            "topology_edges": list(TOPOLOGY_DAG.traffic_dag.edges),
        },
    }


async def _start(phase: TrafficPhase = TrafficPhase.BASELINE) -> dict[str, Any]:
    if NIRANTAR_SIMULATION.running:
        raise HTTPException(409, "Stop the Nirantar bridge simulation before starting the IEMCRP scenario.")
    if TRAFFIC_CONTROLLER.is_running:
        return {"status": "ALREADY_RUNNING", "phase": TRAFFIC_CONTROLLER.current_phase.value}
    restart_wait = TRAFFIC_CONTROLLER.demo_restart_wait_seconds()
    if restart_wait > 0:
        raise HTTPException(429, f"Demo can restart in {restart_wait:.0f} seconds.")
    temperature = cpu_package_temperature_c()
    if temperature is not None and temperature >= DEMO_START_TEMPERATURE_C:
        raise HTTPException(
            503,
            f"Demo load held: CPU package is {temperature:.0f}°C; start allowed below {DEMO_START_TEMPERATURE_C:.0f}°C.",
        )
    await TRAFFIC_CONTROLLER.stop()
    TRAFFIC_CONTROLLER.transactions.clear()
    TRAFFIC_CONTROLLER._update_sliding_stats()
    CONTROL_LOOP.history.clear()
    CONTROL_LOOP.cycle_id = None
    CONTROL_LOOP.last_cycle = None
    CONTROL_LOOP.current_action = "NO_OP"
    CONTROL_LOOP.recovery_state = "NOMINAL"
    WARNING_ENGINE.reset()
    with SAFETY_GUARDRAILS.lock:
        SAFETY_GUARDRAILS.last_executed_time.clear()
    STREAM_BROADCASTER.publish("demo_reset", {"portal_id": "college_portal"})
    DB_POOL.set_fault_pool_exhaustion(False)
    DB_POOL.set_fault_db_latency(0)
    IEMCRP_INFRA_STATE.update(
        {
            "5xx_injection_enabled": False,
            "circuit_breaker_enabled": False,
            "waiting_room_enabled": False,
            "static_fallback_enabled": False,
            "rate_limit_per_sec": 120.0,
        }
    )
    return await TRAFFIC_CONTROLLER.start(
        scenario="IEMCRP_RESULT_DAY_LIVE_DEMO", start_phase=phase, loop_continuously=False
    )


@router.post("/start")
async def start() -> dict[str, Any]:
    _require_demo()
    return await _start()


@router.post("/reset")
async def reset() -> dict[str, Any]:
    _require_demo()
    await TRAFFIC_CONTROLLER.stop()
    DB_POOL.set_fault_pool_exhaustion(False)
    DB_POOL.set_fault_db_latency(0)
    IEMCRP_INFRA_STATE.update(
        {
            "5xx_injection_enabled": False,
            "circuit_breaker_enabled": False,
            "waiting_room_enabled": False,
            "static_fallback_enabled": False,
            "rate_limit_per_sec": 120.0,
        }
    )
    TRAFFIC_CONTROLLER.transactions.clear()
    TRAFFIC_CONTROLLER._update_sliding_stats()
    TRAFFIC_CONTROLLER.current_phase = TrafficPhase.BASELINE
    TRAFFIC_CONTROLLER.current_phase_idx = 0
    TRAFFIC_CONTROLLER.current_vus = 0
    TRAFFIC_CONTROLLER.stop_reason = "RESET"
    CONTROL_LOOP.history.clear()
    CONTROL_LOOP.cycle_id = None
    CONTROL_LOOP.last_cycle = None
    CONTROL_LOOP.current_action = "NO_OP"
    CONTROL_LOOP.recovery_state = "NOMINAL"
    WARNING_ENGINE.reset()
    with SAFETY_GUARDRAILS.lock:
        SAFETY_GUARDRAILS.last_executed_time.clear()
    STREAM_BROADCASTER.publish("demo_reset", {"portal_id": "college_portal"})
    return {"status": "RESET"}


@router.post("/stop")
async def stop() -> dict[str, Any]:
    """Stop generated load at once while retaining the measured story."""
    _require_demo()
    await TRAFFIC_CONTROLLER.stop()
    STREAM_BROADCASTER.publish("demo_stopped", {"portal_id": "college_portal"})
    return {"status": "STOPPED", "workers": 0, "request_cap_per_sec": 12}


@router.post("/pause")
def pause() -> dict[str, Any]:
    _require_demo()
    return TRAFFIC_CONTROLLER.pause()


@router.post("/resume")
def resume() -> dict[str, Any]:
    _require_demo()
    return TRAFFIC_CONTROLLER.resume()


@router.post("/trigger/{scenario}")
async def trigger(scenario: str) -> dict[str, Any]:
    _require_demo()
    scenarios = {
        "result-rush": TrafficPhase.RESULT_RUSH,
        "database": TrafficPhase.SATURATION,
        "rate-limit": TrafficPhase.RESULT_RUSH,
        "circuit-breaker": TrafficPhase.SATURATION,
        "recovery": TrafficPhase.CONTROLLED_RECOVERY,
    }
    if scenario not in scenarios:
        raise HTTPException(400, "Unknown scenario")
    if not TRAFFIC_CONTROLLER.is_running:
        await _start(scenarios[scenario])
    else:
        TRAFFIC_CONTROLLER.set_scenario(phase=scenarios[scenario])
    if scenario == "database":
        DB_POOL.set_fault_db_latency(450)
        DB_POOL.set_fault_pool_exhaustion(True)
    elif scenario == "rate-limit":
        IEMCRP_INFRA_STATE["rate_limit_per_sec"] = 2.0
    elif scenario == "circuit-breaker":
        IEMCRP_INFRA_STATE["5xx_injection_enabled"] = True
        IEMCRP_INFRA_STATE["circuit_breaker_enabled"] = True
    elif scenario == "recovery":
        DB_POOL.set_fault_pool_exhaustion(False)
        DB_POOL.set_fault_db_latency(0)
        IEMCRP_INFRA_STATE["5xx_injection_enabled"] = False
        IEMCRP_INFRA_STATE["circuit_breaker_enabled"] = False
        IEMCRP_INFRA_STATE["rate_limit_per_sec"] = 120.0
    event = {"scenario": scenario, "phase": scenarios[scenario].value, "source": "operator_trigger"}
    STREAM_BROADCASTER.publish("demo_scenario", event)
    return {"status": "TRIGGERED", **event}
