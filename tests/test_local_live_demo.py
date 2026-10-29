"""Local demo contracts around real artifacts, controls, and warning provenance."""
import collections
import pytest

from fastapi.testclient import TestClient

from backend.app import app
from backend.control_plane.explainable_pipeline import EXPLAINABLE_PIPELINE
from backend.control_plane.portal_adapter import IEMCRPAdapter
from backend.control_plane.warning_engine import WarningEngine
from backend.portals.iemcrp_app import MonolithicDatabasePool
from backend.simulation.traffic_controller import (
    DEMO_PHASE_SEQUENCE,
    DEMO_START_TEMPERATURE_C,
    TRAFFIC_CONTROLLER,
    TransactionRecord,
    cpu_package_temperature_c,
)
from backend.streaming.broadcaster import STREAM_BROADCASTER


def test_single_canonical_website():
    with TestClient(app) as client:
        page = client.get("/website")
        assert page.status_code == 200
        assert "Live Resilience Studio" in page.text
        assert 'id="traffic-chart"' in page.text
        assert 'id="architecture-viewer"' in page.text
        assert 'id="tour-dialog"' in page.text
        assert 'id="traffic-recovery"' in page.text
        assert 'id="model-decision"' in page.text
        assert 'id="open-nirantar-direct"' in page.text
        assert client.get("/static/nirantar-live.html").status_code == 200
        assert 'data-view="policy"' not in page.text
        assert 'data-view="response"' not in page.text
        for alias in ("/live-demo", "/app"):
            redirect = client.get(alias, follow_redirects=False)
            assert redirect.status_code == 302
            assert redirect.headers["location"] == "/website"
        nirantar = client.get("/nirantar-demo", follow_redirects=False)
        assert nirantar.headers["location"] == "/website#nirantar"


def test_live_demo_disabled_outside_local_mode(monkeypatch):
    monkeypatch.delenv("PORTALPULSE_DEMO_MODE", raising=False)
    with TestClient(app) as client:
        assert client.get("/api/v1/live-demo/snapshot").status_code == 403


def test_models_and_cycle_are_real_in_local_mode(monkeypatch):
    monkeypatch.setenv("PORTALPULSE_DEMO_MODE", "1")
    with TestClient(app) as client:
        r = client.get("/api/v1/live-demo/snapshot")
        assert r.status_code == 200
        data = r.json()
        assert all(data["models"][key] for key in ("m2_loaded", "m3_loaded", "m4_loaded", "m5_loaded"))
        assert data["models"]["m5_layers"] == [13, 128, 256, 128, 64, 11]
        STREAM_BROADCASTER.reset()
        before_events = STREAM_BROADCASTER.get_stats()["event_type_counts"].get("pipeline_stage", 0)
        cycle = EXPLAINABLE_PIPELINE.run_cycle(portal_id="college_portal")
        assert STREAM_BROADCASTER.get_stats()["event_type_counts"].get("pipeline_stage", 0) > before_events
        assert all(cycle.models[key].status == "COMPLETE" for key in ("M2", "M3", "M4", "M5", "M6"))
        assert cycle.action_recommendation["input_feature_vector"]
        assert len(cycle.action_recommendation["all_action_probabilities"]) == 11
        assert cycle.causal_path


def test_scenario_reset_and_actual_transactions(monkeypatch):
    temperature = cpu_package_temperature_c()
    if temperature is not None and temperature >= DEMO_START_TEMPERATURE_C:
        pytest.skip("Local CPU is too hot for a traffic-generating test")
    monkeypatch.setenv("PORTALPULSE_DEMO_MODE", "1")
    with TestClient(app) as client:
        assert client.post("/api/v1/live-demo/start").json()["status"] == "STARTED"
        assert client.get("/api/v1/live-demo/snapshot").json()["traffic"]["is_running"]
        assert [p.value for p in TRAFFIC_CONTROLLER.phase_sequence] == [p.value for p in DEMO_PHASE_SEQUENCE]
        assert TRAFFIC_CONTROLLER.loop_continuously is True
        assert client.post("/api/v1/live-demo/start").json()["status"] == "ALREADY_RUNNING"
        assert client.post("/api/v1/live-demo/trigger/result-rush").status_code == 200
        assert client.post("/api/v1/live-demo/pause").json()["status"] == "PAUSED"
        assert client.post("/api/v1/live-demo/trigger/database").json()["status"] == "TRIGGERED"
        assert TRAFFIC_CONTROLLER.is_paused is False
        assert client.post("/api/v1/live-demo/pause").json()["status"] == "PAUSED"
        assert client.post("/api/v1/live-demo/resume").json()["status"] == "RESUMED"
        assert client.post("/api/v1/live-demo/stop").json()["status"] == "STOPPED"
        assert not TRAFFIC_CONTROLLER.is_running
        assert client.post("/api/v1/live-demo/reset").json()["status"] == "RESET"
        assert not TRAFFIC_CONTROLLER.is_running
        assert TRAFFIC_CONTROLLER.current_phase.value == "BASELINE"


def test_hot_start_keeps_idle_history_and_generates_no_load(monkeypatch):
    import backend.simulation.live_demo as live_demo

    monkeypatch.setenv("PORTALPULSE_DEMO_MODE", "1")
    monkeypatch.setattr(live_demo, "cpu_package_temperature_c", lambda: 91.0)
    with TestClient(app) as client:
        before = client.get("/api/v1/live-demo/snapshot").json()
        response = client.post("/api/v1/live-demo/start")
        after = client.get("/api/v1/live-demo/snapshot").json()
        assert response.status_code == 503
        assert "CPU package is 91°C" in response.json()["detail"]
        assert after["traffic"]["is_running"] is False
        assert after["history"] == before["history"]
        assert after["latest"] == before["latest"]


def test_warning_requires_observed_condition():
    engine = WarningEngine()
    cycle = EXPLAINABLE_PIPELINE.run_cycle(portal_id="college_portal")
    warnings, _ = engine.evaluate(cycle)
    assert not any(w.id == "WARN_HTTP_429_RATE_LIMITING" for w in warnings)


def test_m1_reads_measured_http_window_in_demo(monkeypatch):
    monkeypatch.setenv("PORTALPULSE_DEMO_MODE", "1")
    monkeypatch.setattr(TRAFFIC_CONTROLLER, "is_running", True)
    monkeypatch.setattr(TRAFFIC_CONTROLLER, "stats_rps", 42.5)
    monkeypatch.setattr(TRAFFIC_CONTROLLER, "stats_p50", 21.0)
    monkeypatch.setattr(TRAFFIC_CONTROLLER, "stats_p95", 189.0)
    monkeypatch.setattr(TRAFFIC_CONTROLLER, "stats_p99", 240.0)
    monkeypatch.setattr(TRAFFIC_CONTROLLER, "stats_failure_rate", 25.0)
    monkeypatch.setattr(TRAFFIC_CONTROLLER, "_active_worker_count", 7)
    monkeypatch.setattr(TRAFFIC_CONTROLLER, "in_flight_requests", 3)
    monkeypatch.setattr(TRAFFIC_CONTROLLER, "transactions", collections.deque([
        TransactionRecord(persona="test", endpoint="GET /api/results/query", status=503, latency=189.0, success=False),
    ]))
    telemetry = IEMCRPAdapter().get_telemetry()
    assert telemetry.requests_per_sec == 42.5
    assert telemetry.p95_latency_ms == 189.0
    assert telemetry.error_rate == 0.25
    assert telemetry.http_5xx == 100.0
    assert telemetry.concurrent_requests == 3


def test_db_peak_is_observed_acquisition_not_drawn_noise():
    pool = MonolithicDatabasePool(max_connections=5)
    assert pool.acquire_connection(timeout=0.01)
    assert pool.get_stats()["recent_peak_utilization_percent"] == 20.0
    pool.release_connection()
    stats = pool.get_stats()
    assert stats["utilization_percent"] == 0.0
    assert stats["recent_peak_utilization_percent"] == 20.0


def test_iemcrp_declared_restart_releases_fault():
    from backend.portals.iemcrp_app import DB_POOL, IEMCRP_INFRA_STATE, execute_iemcrp_action

    before_restarts = IEMCRP_INFRA_STATE["pod_restart_count"]
    DB_POOL.set_fault_pool_exhaustion(True)
    assert DB_POOL.get_stats()["utilization_percent"] >= 90
    try:
        result = execute_iemcrp_action({"action": "RESTART_DEGRADED_PODS", "parameters": {}})
        assert result["status"] == "SUCCESS"
        assert DB_POOL.get_stats()["utilization_percent"] < 90
        assert IEMCRP_INFRA_STATE["pod_restart_count"] == before_restarts + 1
    finally:
        DB_POOL.set_fault_pool_exhaustion(False)


def test_replay_clears_demo_cooldown(monkeypatch):
    from backend.m6_safety_layer.guardrails import SAFETY_GUARDRAILS
    from backend.m4_action_intelligence.schema import SREAction
    from backend.simulation import live_demo, traffic_controller

    monkeypatch.setenv("PORTALPULSE_DEMO_MODE", "1")
    monkeypatch.setattr(live_demo, "cpu_package_temperature_c", lambda: 40.0)
    monkeypatch.setattr(traffic_controller, "cpu_package_temperature_c", lambda: 40.0)
    SAFETY_GUARDRAILS.last_executed_time[SREAction.RESTART_DEGRADED_PODS] = 999999.0
    with TestClient(app) as client:
        assert client.post("/api/v1/live-demo/start").status_code == 200
        assert SREAction.RESTART_DEGRADED_PODS not in SAFETY_GUARDRAILS.last_executed_time
        client.post("/api/v1/live-demo/reset")


def test_recovery_event_requires_measured_m7_verification(monkeypatch):
    from datetime import datetime, timezone
    from backend.control_plane.control_loop import ContinuousControlLoop
    from backend.control_plane.explainable_pipeline import ControlCycle

    events = []
    monkeypatch.setattr(WarningEngine, "evaluate", lambda self, cycle: ([], []))
    monkeypatch.setattr(STREAM_BROADCASTER, "publish_recovery", events.append)
    base = ControlCycle(
        cycle_id="cycle_test", timestamp=datetime.now(timezone.utc).isoformat(),
        portal_id="college_portal", input_telemetry={}, forecast={}, anomaly={},
        rca={}, causal_path=[], action_recommendation={}, safety_validation={},
        pre_metrics={"p95_ms": 1200},
    )
    loop = ContinuousControlLoop()
    loop._broadcast_cycle(base)
    assert events == []

    verified = base.model_copy(update={
        "recommended_action": "SCALE_OUT_WORKERS",
        "actuation_status": "EXECUTED",
        "verification_status": "RECOVERY_VERIFIED",
        "post_metrics": {"p95_ms": 800},
    })
    loop._broadcast_cycle(verified)
    assert len(events) == 1
    assert events[0]["current_result"] == "p95 1.20s → 0.80s"


def test_executed_action_is_verified_using_next_measured_window(monkeypatch):
    from datetime import datetime, timezone
    from backend.control_plane.control_loop import ContinuousControlLoop
    from backend.control_plane.explainable_pipeline import ControlCycle

    events = []
    monkeypatch.setattr(STREAM_BROADCASTER, "publish_recovery", events.append)
    common = dict(
        timestamp=datetime.now(timezone.utc).isoformat(), portal_id="college_portal",
        input_telemetry={}, forecast={}, anomaly={}, rca={}, causal_path=[],
        action_recommendation={}, safety_validation={}, models={},
    )
    prior = ControlCycle(
        cycle_id="cycle_before", **common, recommended_action="RESTART_DEGRADED_PODS",
        actuation_status="EXECUTED", verification_status="OBSERVING",
        pre_metrics={"p95_ms": 300, "errors": 0.2, "db_connections": 100},
    )
    current = ControlCycle(
        cycle_id="cycle_after", **common,
        pre_metrics={"p95_ms": 120, "errors": 0.0, "db_connections": 75},
    )
    loop = ContinuousControlLoop()
    loop.history.append(prior)
    loop._verify_pending_actions(current)
    assert prior.actuation_status == "EXECUTED"
    assert prior.verification_status == "RECOVERY_VERIFIED"
    assert prior.post_metrics["db_connections"] == 75
    assert events[0]["follow_up_cycle"] == "cycle_after"
