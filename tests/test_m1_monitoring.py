"""Unit and integration tests for PortalPulse Module 1 (Monitoring & Ingestion)."""

from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app import app
from backend.m1_monitoring.collector import TelemetryCollector
from backend.m1_monitoring.portal_simulator import PortalSimulator
from backend.m1_monitoring.schema import (
    HealthStatus,
    RawTelemetry,
    ScenarioConfig,
    ScenarioType,
)

client = TestClient(app)


def test_raw_telemetry_schema():
    """Verify that RawTelemetry properly validates the 15 required fields."""
    raw = RawTelemetry(
        active_users=12500,
        requests_per_sec=850.5,
        cpu_percent=45.2,
        ram_percent=52.0,
        network_in=65.2,
        network_out=145.0,
        response_time=210.5,
        throughput=848.0,
        error_rate=0.002,
        http_5xx=1.5,
        db_latency=35.0,
        db_connections=42.0,
        queue_length=5,
        service_instances=4,
    )
    assert raw.active_users == 12500
    assert raw.requests_per_sec == 850.5
    assert raw.cpu_percent == 45.2
    assert raw.db_connections == 42.0
    assert raw.service_instances == 4


def test_portal_simulator_nominal_vs_rush():
    """Verify simulator behavior across NORMAL and RESULT_RUSH scenarios."""
    sim = PortalSimulator()

    # Step 1: Normal
    sim.update_config(ScenarioConfig(scenario_type=ScenarioType.NORMAL))
    step_normal = sim.generate_step()
    assert step_normal.active_users >= 5000
    assert step_normal.cpu_percent < 80.0
    assert step_normal.response_time < 500.0

    # Step 2: Result rush
    sim.update_config(ScenarioConfig(scenario_type=ScenarioType.RESULT_RUSH, user_multiplier=1.5))
    # Step a few times to simulate rush build-up
    for _ in range(5):
        step_rush = sim.generate_step()

    assert step_rush.active_users > step_normal.active_users
    assert step_rush.requests_per_sec > step_normal.requests_per_sec
    assert step_rush.db_connections > 50.0


def test_collector_feature_engineering_and_sla():
    """Test ring buffer, lag calculations, and SLA breach tagging."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        test_db = Path(tmp_dir) / "test_telemetry.db"
        collector = TelemetryCollector(max_buffer_size=100, db_path=test_db)

        # Ingest 6 observations with increasing CPU and latency
        for i in range(1, 7):
            raw = RawTelemetry(
                active_users=1000 * i,
                requests_per_sec=100.0 * i,
                cpu_percent=20.0 + (i * 12.0),  # Reaches 92% at i=6
                ram_percent=40.0 + (i * 5.0),
                network_in=10.0 * i,
                network_out=25.0 * i,
                response_time=100.0 * i,  # Reaches 600ms at i=6
                throughput=98.0 * i,
                error_rate=0.001 * i,
                http_5xx=0.5 * i,
                db_latency=20.0 * i,
                db_connections=15.0 * i,  # Reaches 90% at i=6
                queue_length=10 * i,
                service_instances=4,
            )
            status = collector.record_telemetry(raw)

        # At i=6, CPU is 92.0% (limit 85%) and DB pool is 90.0% -> CRITICAL
        assert status.health_status == HealthStatus.CRITICAL
        assert status.sla_cpu_breached is True
        assert status.sla_db_breached is True

        # Check derived features
        derived = status.derived
        assert derived.cpu_lag_1 == 80.0  # i=5 was 20 + 60 = 80
        assert derived.cpu_lag_5 == 20.0 + 12.0  # i=1 was 32
        assert derived.rolling_rps_5m > 0
        assert derived.traffic_growth_rate > 0

        # Check history
        hist = collector.get_history(limit=5)
        assert len(hist) == 5
        assert hist[-1].cpu_percent == 92.0


def test_fastapi_endpoints():
    """Test full HTTP API endpoints on FastAPI app."""
    # 1. Health check
    res_root = client.get("/")
    assert res_root.status_code == 200
    assert res_root.json()["status"] == "ONLINE"

    res_health = client.get("/health")
    assert res_health.status_code == 200
    assert res_health.json()["status"] == "HEALTHY"

    # 2. Seed simulation
    res_seed = client.post("/api/v1/portal/seed?steps=10")
    assert res_seed.status_code == 200
    assert res_seed.json()["status"] == "success"
    assert res_seed.json()["seeded_steps"] == 10

    # 3. Live telemetry
    res_live = client.get("/api/v1/telemetry/live")
    assert res_live.status_code == 200
    data = res_live.json()
    assert "raw" in data
    assert "derived" in data
    assert "health_status" in data
    assert data["raw"]["active_users"] > 0

    # 4. History
    res_hist = client.get("/api/v1/telemetry/history?limit=10")
    assert res_hist.status_code == 200
    assert len(res_hist.json()) <= 10

    # 5. Set Scenario
    res_scen = client.post(
        "/api/v1/portal/scenario",
        json={
            "scenario_type": "DATABASE_LOCK_JAM",
            "user_multiplier": 1.2,
            "service_instances": 6,
        },
    )
    assert res_scen.status_code == 200
    assert res_scen.json()["active_scenario"] == "DATABASE_LOCK_JAM"

    # 6. Step simulation
    res_step = client.post("/api/v1/portal/step")
    assert res_step.status_code == 200
    assert res_step.json()["scenario"] == "DATABASE_LOCK_JAM"

    # 7. Telemetry summary
    res_sum = client.get("/api/v1/telemetry/summary")
    assert res_sum.status_code == 200
    assert "latency_p50_ms" in res_sum.json()
    assert "mean_rps" in res_sum.json()
