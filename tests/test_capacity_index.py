"""Unit tests for Portal Capacity Index (PCI) and Multi-Tier Headroom Engine."""

from starlette.testclient import TestClient

from backend.app import app
from backend.control_plane.capacity_index import CAPACITY_ENGINE, PCIState
from portalpulse_sdk.schema import UniversalTelemetry


def test_capacity_index_nominal_safe():
    telemetry = UniversalTelemetry(
        portal_id="test_portal",
        timestamp="2026-09-09T12:00:00Z",
        active_users=500,
        requests_per_sec=45.0,
        cpu_percent=15.0,
        ram_percent=25.0,
        latency_ms=18.0,
        throughput=45.0,
        error_rate=0.0,
        http_5xx=0.0,
        db_latency_ms=2.0,
        db_connections=12.0,
        queue_length=0,
        service_instances=8,
        network_in_mb=1.2,
        network_out_mb=2.4,
        db_connection_limit=200,
    )

    report = CAPACITY_ENGINE.compute_capacity_index(telemetry)
    assert report.pci < 0.70
    assert report.state == PCIState.SAFE
    assert report.headroom_users > 0
    assert report.sustainable_users > report.current_users
    assert "SAFE" in report.state.value


def test_capacity_index_database_bottleneck_detection():
    # Simulate heavy DB load where db_connections is high relative to users
    telemetry = UniversalTelemetry(
        portal_id="db_stressed_portal",
        timestamp="2026-09-09T12:00:00Z",
        active_users=1800,
        requests_per_sec=280.0,
        cpu_percent=45.0,
        ram_percent=50.0,
        latency_ms=85.0,
        throughput=280.0,
        error_rate=0.01,
        http_5xx=0.0,
        db_latency_ms=45.0,
        db_connections=92.5,  # 92.5% DB pool saturation!
        queue_length=5,
        service_instances=8,
        network_in_mb=10.0,
        network_out_mb=25.0,
        db_connection_limit=200,
    )

    report = CAPACITY_ENGINE.compute_capacity_index(telemetry)
    assert report.limiting_bottleneck == "DATABASE_POOL"
    assert report.pci > 0.85
    assert report.state in (PCIState.CRITICAL, PCIState.OVER_CAPACITY)


def test_capacity_index_extreme_over_capacity():
    telemetry = UniversalTelemetry(
        portal_id="overload_portal",
        timestamp="2026-09-09T12:00:00Z",
        active_users=12000,
        requests_per_sec=2200.0,
        cpu_percent=95.0,
        ram_percent=88.0,
        latency_ms=1200.0,
        throughput=1800.0,
        error_rate=0.15,
        http_5xx=25.0,
        db_latency_ms=150.0,
        db_connections=98.0,
        queue_length=450,
        service_instances=8,
        network_in_mb=120.0,
        network_out_mb=280.0,
        db_connection_limit=200,
    )

    report = CAPACITY_ENGINE.compute_capacity_index(telemetry)
    assert report.pci > 1.0
    assert report.state == PCIState.OVER_CAPACITY
    assert report.headroom_users < 0
    assert "OVER CAPACITY" in report.recommendation


def test_capacity_index_api_endpoint():
    client = TestClient(app)
    res = client.get("/api/v1/portals/nirantar/capacity-index")
    assert res.status_code == 200
    data = res.json()
    assert data["portal_id"] == "nirantar"
    assert "pci" in data
    assert "state" in data
    assert "headroom_users" in data
    assert "limiting_bottleneck" in data
    assert "breakdown" in data
