"""End-to-End Test for Exam Day Simulation & Closed-Loop Autonomous Recovery."""

import anyio
import pytest
from starlette.testclient import TestClient

from backend.app import app
from backend.simulation.exam_day_runner import EXAM_DAY_RUNNER


@pytest.mark.anyio
async def test_exam_day_autonomous_closed_loop_lifecycle():
    # Start scenario with accelerated delay scale for fast test execution
    res = EXAM_DAY_RUNNER.start_scenario(
        scenario_name="TEST_3_EXAM_STAMPEDE",
        portal_id="nirantar",
        step_delay_scale=0.02,
    )
    assert res["status"] in ("STARTED", "ALREADY_RUNNING")

    # Await scenario lifecycle completion
    for _ in range(40):
        status = EXAM_DAY_RUNNER.get_status()
        if not status["is_running"] and status["certificate"] is not None:
            break
        await anyio.sleep(0.1)

    final_status = EXAM_DAY_RUNNER.get_status()
    cert = final_status["certificate"]
    assert cert is not None
    assert cert["status"] == "PASS"
    assert cert["sustainable_rps"] > 100.0
    assert cert["max_safe_concurrent_users"] >= 5000
    assert "ENABLE_WAITING_ROOM" in cert["autonomous_actions_executed"]
    assert cert["sla_compliance_pct"] >= 99.0
    assert "PORTALPULSE OFFICIAL CAPACITY CERTIFICATE" in cert["formatted_certificate"]


def test_exam_day_api_endpoints():
    client = TestClient(app)

    # Test status endpoint
    res_status = client.get("/api/v1/capacity-benchmark/exam-day/status")
    assert res_status.status_code == 200
    data = res_status.json()
    assert "is_running" in data
    assert "events_count" in data

    # Test stop endpoint
    res_stop = client.post("/api/v1/capacity-benchmark/exam-day/stop")
    assert res_stop.status_code == 200
    assert res_stop.json()["status"] == "STOPPED"
