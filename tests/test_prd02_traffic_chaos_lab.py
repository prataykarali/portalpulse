"""Tests for PRD-02 Autonomous Traffic, Capacity & Chaos Lab."""

import pytest
from backend.m8_chaos_lab.chaos_engine import CHAOS_LAB
from backend.m8_chaos_lab.schema import ChaosInjectionRequest, ChaosScenario
from backend.simulation.scenario_history import SCENARIO_HISTORY, ScenarioRunRecord


def test_ten_chaos_scenarios_exist():
    expected_scenarios = [
        "NORMAL", "TRAFFIC_SPIKE", "DB_LATENCY", "DB_CONNECTION_EXHAUSTION",
        "CACHE_MISS_STORM", "WORKER_FAILURE", "CPU_PRESSURE", "MEMORY_PRESSURE",
        "NETWORK_LATENCY", "HTTP_5XX_BURST", "DEPENDENCY_FAILURE"
    ]
    for s in expected_scenarios:
        assert s in ChaosScenario.__members__


def test_chaos_lab_injection_and_stop():
    req = ChaosInjectionRequest(
        portal_id="college_portal",
        scenario=ChaosScenario.DB_CONNECTION_EXHAUSTION,
        intensity=1.0,
        duration_seconds=10
    )
    res = CHAOS_LAB.inject_chaos(req)
    assert res.is_active is True
    assert res.active_scenario == ChaosScenario.DB_CONNECTION_EXHAUSTION
    assert res.is_real_local_fault is True
    assert res.provenance_tag == "REAL_LOCAL_FAULT"

    stop_res = CHAOS_LAB.stop_chaos()
    assert stop_res.is_active is False
    assert stop_res.active_scenario == ChaosScenario.NORMAL


def test_scenario_history_manager():
    rec = ScenarioRunRecord(
        portal_id="nirantar",
        scenario_name="Test Run Alpha",
        scenario_type="CUSTOM_BUILDER",
        duration_sec=30.0,
        metrics={"peak_rps": 520.0, "p95_latency_ms": 310.0, "error_rate_pct": 0.01}
    )
    saved = SCENARIO_HISTORY.record_run(rec)
    assert saved.scenario_id == rec.scenario_id

    fetched = SCENARIO_HISTORY.get_run(rec.scenario_id)
    assert fetched is not None
    assert fetched.metrics["peak_rps"] == 520.0

    all_runs = SCENARIO_HISTORY.list_runs()
    assert len(all_runs) >= 1
