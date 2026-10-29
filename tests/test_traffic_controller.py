"""Unit and integration tests for the continuous autonomous TrafficController and IEMCRP load generation.

Tests:
1. Start/stop traffic controller lifecycle.
2. GET /api/v1/traffic/status contains all required observability metrics.
3. Realistic persona execution across the 5 personas and 5 endpoints.
4. Continuous transaction accounting in rolling buffer.
5. Phase transition via POST /api/v1/traffic/scenario across 8 phases.
6. Pause and resume controls.
7. Clear distinction between REAL REQUEST LOAD and VIRTUAL USER SCENARIO SCALE.
"""

from __future__ import annotations

import asyncio
import time
import pytest
from starlette.testclient import TestClient

from backend.app import app
from backend.simulation.traffic_controller import (
    DEMO_PHASE_SEQUENCE,
    DEMO_MAX_REQUESTS_PER_SECOND,
    TRAFFIC_CONTROLLER,
    TrafficController,
    TrafficPhase,
    demo_wave_request_rate,
)


def test_demo_phase_wrap_stays_running_and_clears_faults(monkeypatch):
    monkeypatch.setenv("PORTALPULSE_DEMO_MODE", "1")
    controller = TrafficController()
    controller.scenario_name = "IEMCRP_RESULT_DAY_LIVE_DEMO"
    controller.phase_sequence = DEMO_PHASE_SEQUENCE
    controller.current_phase_idx = len(DEMO_PHASE_SEQUENCE) - 1
    controller.is_running = True
    controller.loop_continuously = True
    cleared = []
    monkeypatch.setattr(controller, "_clear_demo_faults", lambda: cleared.append(True))
    asyncio.run(controller._advance_to_next_phase())
    assert controller.is_running
    assert controller.current_phase is TrafficPhase.BASELINE
    assert cleared == [True]


@pytest.fixture(autouse=True)
def ensure_traffic_clean_shutdown():
    """Guarantee TRAFFIC_CONTROLLER is stopped after every test."""
    yield
    if TRAFFIC_CONTROLLER.is_running:
        asyncio.run(TRAFFIC_CONTROLLER.stop())


def test_traffic_status_endpoint_contract():
    """GET /api/v1/traffic/status must expose all required schema fields."""
    with TestClient(app) as client:
        res = client.get("/api/v1/traffic/status")
        assert res.status_code == 200
        data = res.json()
        required_fields = [
            "phase",
            "target_vus",
            "current_vus",
            "rps",
            "success_rate",
            "failure_rate",
            "p50",
            "p95",
            "p99",
            "elapsed",
            "scenario",
            "real_requests_per_sec",
            "virtual_user_scale",
            "real_concurrency_workers",
            "scale_ratio",
            "is_running",
            "is_paused",
        ]
        for f in required_fields:
            assert f in data, f"Missing required field {f} in /api/v1/traffic/status"


def test_traffic_lifecycle_and_continuous_accounting():
    """Starting traffic should execute real transactions hitting IEMCRP endpoints."""
    with TestClient(app) as client:
        # Start traffic scenario
        start_res = client.post(
            "/api/v1/traffic/start",
            json={"scenario": "CONTINUOUS_RESULT_DAY", "start_phase": "BASELINE"},
        )
        assert start_res.status_code == 200
        assert start_res.json()["status"] in ("STARTED", "ALREADY_RUNNING")

        # Allow workers to execute transactions against IEMCRP
        time.sleep(1.5)

        # Inspect status
        status_res = client.get("/api/v1/traffic/status")
        assert status_res.status_code == 200
        status_data = status_res.json()
        assert status_data["is_running"] is True
        assert status_data["phase"] == "BASELINE"
        assert status_data["target_vus"] == 50

        # Inspect rolling transaction buffer
        tx_res = client.get("/api/v1/traffic/transactions?limit=25")
        assert tx_res.status_code == 200
        transactions = tx_res.json()
        assert isinstance(transactions, list)
        assert len(transactions) > 0

        # Validate transaction schema and actual endpoint distribution
        sample = transactions[-1]
        assert "timestamp" in sample
        assert "persona" in sample
        assert "endpoint" in sample
        assert "status" in sample
        assert "latency" in sample
        assert "success" in sample
        assert sample["latency"] >= 0

        # Check endpoints hit match the required 5
        endpoints_seen = {t["endpoint"] for t in transactions}
        valid_prefixes = (
            "GET /api/student/dashboard",
            "GET /api/exam/questions",
            "POST /api/exam/submit",
            "GET /api/results/query",
            "POST /api/faculty/grades/save",
        )
        assert any(ep.startswith(valid_prefixes) for ep in endpoints_seen)

        # Stop traffic
        stop_res = client.post("/api/v1/traffic/stop")
        assert stop_res.status_code == 200
        assert stop_res.json()["status"] == "STOPPED"


def test_traffic_phase_transitions_and_vu_scaling():
    """POST /api/v1/traffic/scenario should smoothly transition phases and scale VUs."""
    with TestClient(app) as client:
        client.post("/api/v1/traffic/start")

        # Test phase transitions across conceptual VU scales: 50, 500, 2500, 5000, 8500, 12500
        test_scales = [
            (TrafficPhase.RAMP, 500),
            (TrafficPhase.RESULT_RUSH, 2500),
            (TrafficPhase.SATURATION, 12500),
            (TrafficPhase.CONTROLLED_RECOVERY, 5000),
            (TrafficPhase.SUSTAINED_LOAD, 2500),
            (TrafficPhase.NORMAL, 50),
        ]

        for ph, vus in test_scales:
            scen_res = client.post(
                "/api/v1/traffic/scenario",
                json={"phase": ph.value, "target_vus": vus, "duration_seconds": 15.0},
            )
            assert scen_res.status_code == 200
            data = scen_res.json()
            assert data["phase"] == ph.value
            assert data["target_vus"] == vus

            status_res = client.get("/api/v1/traffic/status")
            assert status_res.json()["phase"] == ph.value
            assert status_res.json()["target_vus"] == vus
            # Clear distinction check
            assert "conceptual virtual users" in status_res.json()["scale_ratio"]

        client.post("/api/v1/traffic/stop")


def test_traffic_pause_and_resume():
    """POST /api/v1/traffic/pause and resume should properly update paused state."""
    with TestClient(app) as client:
        client.post("/api/v1/traffic/start")

        pause_res = client.post("/api/v1/traffic/pause")
        assert pause_res.status_code == 200
        assert pause_res.json()["status"] == "PAUSED"
        assert client.get("/api/v1/traffic/status").json()["is_paused"] is True

        resume_res = client.post("/api/v1/traffic/resume")
        assert resume_res.status_code == 200
        assert resume_res.json()["status"] == "RESUMED"
        assert client.get("/api/v1/traffic/status").json()["is_paused"] is False

        client.post("/api/v1/traffic/stop")


def test_traffic_alias_routes():
    """Endpoints should also be accessible via /traffic aliases without /api/v1."""
    with TestClient(app) as client:
        res_status = client.get("/traffic/status")
        assert res_status.status_code == 200
        res_tx = client.get("/traffic/transactions?limit=5")
        assert res_tx.status_code == 200


def test_hot_laptop_cannot_start_local_demo(monkeypatch):
    from fastapi import HTTPException
    import backend.simulation.traffic_controller as module

    monkeypatch.setenv("PORTALPULSE_DEMO_MODE", "1")
    monkeypatch.setattr(module, "cpu_package_temperature_c", lambda: 91.0)
    controller = TrafficController()
    with pytest.raises(HTTPException, match="CPU package is 91°C"):
        asyncio.run(controller.start(scenario="IEMCRP_RESULT_DAY_LIVE_DEMO"))
    assert not controller.is_running


def test_public_demo_restart_cooldown_rejects_repeat_start(monkeypatch):
    from fastapi import HTTPException

    monkeypatch.setenv("PORTALPULSE_DEMO_MODE", "1")
    monkeypatch.setenv("PORTALPULSE_DEMO_MIN_RESTART_SECONDS", "180")
    controller = TrafficController()
    controller.last_started_at = time.monotonic()
    with pytest.raises(HTTPException) as error:
        asyncio.run(controller.start(scenario="IEMCRP_RESULT_DAY_LIVE_DEMO"))
    assert error.value.status_code == 429
    assert not controller.is_running


def test_stop_waits_until_generated_workers_exit(monkeypatch):
    monkeypatch.setenv("PORTALPULSE_DEMO_MODE", "1")

    async def scenario():
        controller = TrafficController()
        exited = asyncio.Event()

        async def worker():
            try:
                await asyncio.Future()
            finally:
                exited.set()

        task = asyncio.create_task(worker())
        await asyncio.sleep(0)
        controller.is_running = True
        controller._worker_tasks = [task]
        await controller.stop()
        assert exited.is_set()
        assert task.done()
        assert controller._worker_tasks == []
        assert controller.stop_reason == "MANUAL_STOP"

    asyncio.run(scenario())


def test_demo_waves_have_clear_lulls_without_exceeding_request_cap():
    for phase in TrafficPhase:
        lull = demo_wave_request_rate(phase, 2, 0.5)
        burst = demo_wave_request_rate(phase, 3, 0.5)
        assert 0 < lull < burst <= DEMO_MAX_REQUESTS_PER_SECOND
        assert demo_wave_request_rate(phase, 3, 99) <= DEMO_MAX_REQUESTS_PER_SECOND
