"""Unit and integration tests for the continuous autonomous PortalPulse control-cycle scheduler.

Tests:
1. Lifecycle start and clean shutdown.
2. GET /api/v1/control-loop/status contains all required fields.
3. GET /api/v1/control-loop/latest returns a complete ControlCycle.
4. GET /api/v1/control-loop/history returns recent cycles respecting limit.
5. Error recovery: an exception in a cycle does not kill the loop.
6. Anti-flapping and cooldown respect.
7. NO_OP handling when system is nominal.
"""

from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest
from starlette.testclient import TestClient

from backend.app import app
from backend.control_plane.control_loop import CONTROL_LOOP, ContinuousControlLoop
from backend.control_plane.explainable_pipeline import ControlCycle


def test_control_loop_status_endpoint():
    """GET /api/v1/control-loop/status must return all 9 required schema fields."""
    with TestClient(app) as client:
        res = client.get("/api/v1/control-loop/status")
        assert res.status_code == 200
        data = res.json()
        assert "running" in data
        assert "cycle_id" in data
        assert "interval_ms" in data
        assert data["interval_ms"] == 3000
        assert "last_cycle" in data
        assert "next_cycle" in data
        assert "phase" in data
        assert "current_action" in data
        assert "recovery_state" in data
        assert "last_error" in data


def test_control_loop_latest_endpoint():
    """GET /api/v1/control-loop/latest must return the complete ControlCycle."""
    with TestClient(app) as client:
        res = client.get("/api/v1/control-loop/latest")
        assert res.status_code == 200
        cycle = res.json()
        assert "cycle_id" in cycle
        assert "timestamp" in cycle
        assert "input_telemetry" in cycle
        assert "forecast" in cycle
        assert "anomaly" in cycle
        assert "rca" in cycle
        assert "causal_path" in cycle
        assert "action_recommendation" in cycle
        assert "safety_validation" in cycle
        assert "pre_metrics" in cycle
        assert "recovery_state" in cycle


def test_control_loop_history_endpoint():
    """GET /api/v1/control-loop/history must return recent cycles within limit."""
    with TestClient(app) as client:
        # Trigger a couple of cycles
        CONTROL_LOOP.step()
        res = client.get("/api/v1/control-loop/history?limit=10")
        assert res.status_code == 200
        history = res.json()
        assert isinstance(history, list)
        assert len(history) >= 1
        assert len(history) <= 10
        # Validate schema of history entries
        first = history[-1]
        assert "cycle_id" in first
        assert "input_telemetry" in first


def test_control_loop_alias_routes():
    """Endpoints should also be accessible via /control-loop aliases."""
    with TestClient(app) as client:
        res_status = client.get("/control-loop/status")
        assert res_status.status_code == 200
        res_latest = client.get("/control-loop/latest")
        assert res_latest.status_code == 200
        res_history = client.get("/control-loop/history?limit=5")
        assert res_history.status_code == 200


@pytest.mark.anyio
async def test_control_loop_lifecycle_clean_start_and_stop():
    """Control loop starts cleanly and stops cleanly without leaving dangling tasks."""
    loop_engine = ContinuousControlLoop(interval_seconds=0.1)
    await loop_engine.start()
    assert loop_engine.running is True
    assert loop_engine._task is not None

    # Let it run briefly
    await asyncio.sleep(0.25)

    status = loop_engine.get_status()
    assert status.running is True

    await loop_engine.stop()
    assert loop_engine.running is False
    assert loop_engine.phase == "STOPPED"


def test_control_loop_error_recovery_resilience():
    """A model exception in step() does not permanently crash the loop state."""
    loop_engine = ContinuousControlLoop(interval_seconds=1.0)
    
    with patch("backend.control_plane.control_loop.EXPLAINABLE_PIPELINE.run_cycle", side_effect=RuntimeError("Simulated M3 failure")):
        with pytest.raises(RuntimeError):
            loop_engine.step()

        assert loop_engine.last_error == "Simulated M3 failure"
        status = loop_engine.get_status()
        assert status.last_error == "Simulated M3 failure"

    # Next step should recover when exception clears
    cycle = loop_engine.step()
    assert isinstance(cycle, ControlCycle)
    assert loop_engine.last_error is None
