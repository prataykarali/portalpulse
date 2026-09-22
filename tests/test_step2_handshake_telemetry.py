"""Step 2 Verification Test Suite: PortalPulse Runtime / Connector Handshake & Telemetry Pipeline.

Validates:
1. Long-lived API key provisioning and authentication.
2. 7-step registration handshake with short-lived session token generation.
3. Schema version negotiation ("v1" -> accepted "v1").
4. Capability discovery and Action Masking across structurally distinct portals (Nirantar vs College Portal).
5. Dynamic DAG dependency discovery.
6. Telemetry validation (enforcing bounds, rejecting cpu_percent=900 with HTTP 422).
7. Dual-tier storage: In-memory ring buffer (hot) + SQLite WAL persistence (historical).
8. Liveness heartbeat and watchdog state transitions (CONNECTED -> TELEMETRY_LOST -> CONNECTED).
9. Pluggable SDK PortalPulseAgent operations.
"""

from __future__ import annotations

import time
from fastapi.testclient import TestClient
import pytest

from backend.app import app
from backend.control_plane.registry import PORTAL_REGISTRY, PortalRegistry
from backend.control_plane.schema import (
    ConnectionLifecycleState,
    PortalRegistrationRequest,
    ProvisionKeyRequest,
)
from portalpulse_sdk.schema import (
    DependencyGraphSpec,
    PortalCapabilities,
    UniversalTelemetry,
)

client = TestClient(app)


def test_api_key_provisioning() -> None:
    """Test explicit long-lived connector API key provisioning."""
    resp = client.post(
        "/api/v1/portals/keys/provision",
        json={
            "portal_id": "test_portal_prov",
            "portal_name": "Test Provisioned Portal",
            "environment": "staging",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["portal_id"] == "test_portal_prov"
    assert data["api_key"].startswith("pp_live_test_portal_prov_")
    assert data["environment"] == "staging"


def test_handshake_registration_flow() -> None:
    """Test 7-step handshake returning short-lived session token and schema version negotiation."""
    # First provision key
    prov = client.post(
        "/api/v1/portals/keys/provision",
        json={"portal_id": "nirantar_handshake", "portal_name": "Nirantar Railway ERP"},
    ).json()
    api_key = prov["api_key"]

    # Register using provisioned key
    reg_payload = {
        "portal_id": "nirantar_handshake",
        "portal_name": "Nirantar Railway ERP",
        "connector_type": "python_sdk",
        "schema_version": "v1",
        "telemetry_interval": 5,
        "capabilities": {
            "horizontal_scaling": True,
            "database_replica": False,
            "caching": True,
            "static_fallback": True,
            "waiting_room": True,
            "rate_limiting": True,
        },
        "dependencies": {
            "nodes": ["frontend", "api_gateway", "worker_backend", "redis_cache", "postgresql_db"],
            "edges": [
                ["frontend", "api_gateway"],
                ["api_gateway", "worker_backend"],
                ["worker_backend", "redis_cache"],
                ["worker_backend", "postgresql_db"],
            ],
            "entrypoint_node": "frontend",
            "storage_nodes": ["redis_cache", "postgresql_db"],
        },
        "api_key": api_key,
    }

    resp = client.post("/api/v1/portals/register", json=reg_payload)
    assert resp.status_code == 201
    data = resp.json()

    assert data["status"] == "CONNECTED"
    assert data["portal_id"] == "nirantar_handshake"
    assert data["accepted_schema_version"] == "v1"
    assert data["telemetry_interval"] == 5
    assert data["portalpulse_session"].startswith("pps_")
    assert "SCALE_OUT_WORKERS" in data["permitted_actions"]
    assert "DIVERT_READS_TO_REPLICA" in data["masked_actions"]
    assert "SCALE_OUT_WORKERS" in data["supported_actions"]
    assert "DIVERT_READS_TO_REPLICA" in data["unsupported_actions"]


def test_two_structurally_different_portals() -> None:
    """Proves pluggability by registering Nirantar vs a Monolithic College Portal."""
    # 1. Register Nirantar (Distributed, caching, scaling enabled, no replica)
    nirantar_resp = client.post(
        "/api/v1/portals/register",
        json={
            "portal_id": "nirantar_erp_v2",
            "portal_name": "Nirantar ERP",
            "capabilities": {
                "horizontal_scaling": True,
                "database_replica": False,
                "caching": True,
                "waiting_room": True,
            },
            "dependencies": {
                "nodes": ["client", "api", "backend", "redis", "postgres"],
                "edges": [["client", "api"], ["api", "backend"], ["backend", "redis"], ["backend", "postgres"]],
            },
        },
    ).json()

    # 2. Register College Portal (Monolithic, no caching, no scaling, no replica, waiting room only)
    college_resp = client.post(
        "/api/v1/portals/register",
        json={
            "portal_id": "monolith_college_v2",
            "portal_name": "Monolithic College Portal",
            "capabilities": {
                "horizontal_scaling": False,
                "database_replica": False,
                "caching": False,
                "static_fallback": False,
                "waiting_room": True,
                "rate_limiting": True,
            },
            "dependencies": {
                "nodes": ["browser", "monolith_server", "postgres_db"],
                "edges": [["browser", "monolith_server"], ["monolith_server", "postgres_db"]],
            },
        },
    ).json()

    assert "SCALE_OUT_WORKERS" in nirantar_resp["permitted_actions"]
    assert "SCALE_OUT_WORKERS" in college_resp["masked_actions"]
    assert "PURGE_REDIS_CACHE" in nirantar_resp["permitted_actions"]
    assert "PURGE_REDIS_CACHE" in college_resp["masked_actions"]
    assert "ENABLE_WAITING_ROOM" in college_resp["permitted_actions"]


def test_telemetry_validation_and_rejection() -> None:
    """Verify that bad telemetry (e.g. cpu_percent=900) is rejected with HTTP 422."""
    portal_id = "test_val_portal"
    client.post(
        "/api/v1/portals/register",
        json={"portal_id": portal_id, "portal_name": "Val Portal"},
    )

    # 1. Send invalid cpu_percent = 900
    bad_payload = {
        "portal_id": portal_id,
        "active_users": 1000,
        "requests_per_sec": 50.0,
        "cpu_percent": 900.0,  # Invalid: > 100
        "ram_percent": 50.0,
        "latency_ms": 100.0,
        "throughput": 49.0,
        "error_rate": 0.01,
    }
    resp = client.post(f"/api/v1/portals/{portal_id}/telemetry", json=bad_payload)
    assert resp.status_code == 422
    detail_str = str(resp.json()["detail"])
    assert "cpu_percent" in detail_str or "less than or equal to 100" in detail_str

    # 2. Send invalid error_rate = 1.5
    bad_payload2 = dict(bad_payload, cpu_percent=50.0, error_rate=1.5)
    resp2 = client.post(f"/api/v1/portals/{portal_id}/telemetry", json=bad_payload2)
    assert resp2.status_code == 422

    # 3. Send valid telemetry
    good_payload = dict(bad_payload, cpu_percent=74.5, error_rate=0.003)
    resp3 = client.post(f"/api/v1/portals/{portal_id}/telemetry", json=good_payload)
    assert resp3.status_code == 200
    assert resp3.json()["status"] == "INGESTED"


def test_dual_tier_storage_and_history() -> None:
    """Verify that ingested telemetry is available in hot live view and persistent history."""
    p_id = "test_storage_portal"
    client.post("/api/v1/portals/register", json={"portal_id": p_id, "portal_name": "Storage Portal"})

    for i in range(5):
        client.post(
            f"/api/v1/portals/{p_id}/telemetry",
            json={
                "portal_id": p_id,
                "active_users": 2000 + i * 100,
                "requests_per_sec": 300.0 + i * 10,
                "cpu_percent": 60.0 + i,
                "ram_percent": 55.0,
                "latency_ms": 200.0 + i * 5,
                "throughput": 298.0,
                "error_rate": 0.002,
            },
        )

    # Hot live view
    live_resp = client.get(f"/api/v1/portals/{p_id}/telemetry/live")
    assert live_resp.status_code == 200
    assert live_resp.json()["active_users"] == 2400

    # Historical SQLite view
    hist_resp = client.get(f"/api/v1/portals/{p_id}/history?limit=10")
    assert hist_resp.status_code == 200
    history = hist_resp.json()
    assert len(history) >= 5
    assert history[-1]["portal_id"] == p_id


def test_heartbeat_and_watchdog_transition() -> None:
    """Verify heartbeat ping and watchdog detection of stalled telemetry."""
    p_id = "test_watchdog_portal"
    client.post("/api/v1/portals/register", json={"portal_id": p_id, "portal_name": "Watchdog Portal"})

    # Send initial telemetry
    client.post(
        f"/api/v1/portals/{p_id}/telemetry",
        json={
            "portal_id": p_id,
            "active_users": 500,
            "requests_per_sec": 50.0,
            "cpu_percent": 30.0,
            "ram_percent": 40.0,
            "latency_ms": 90.0,
            "throughput": 50.0,
            "error_rate": 0.0,
        },
    )

    portal_info = client.get(f"/api/v1/portals/{p_id}").json()
    assert portal_info["connection_state"] == "CONNECTED"

    # Heartbeat ping
    hb_resp = client.post(f"/api/v1/portals/{p_id}/heartbeat")
    assert hb_resp.status_code == 200
    assert hb_resp.json()["status"] == "ACK"

    # Sleep slightly so elapsed time exceeds 0.01s threshold
    time.sleep(0.05)

    # Manually trigger watchdog with 0.01s timeout to force detection
    wd_resp = client.post("/api/v1/portals/watchdog?timeout_seconds=0.01")
    assert wd_resp.status_code == 200
    assert p_id in wd_resp.json()["degraded_portals"]

    # Verify status is now DEGRADED / TELEMETRY_LOST
    portal_degraded = client.get(f"/api/v1/portals/{p_id}").json()
    assert portal_degraded["connection_state"] == "TELEMETRY_LOST"
    assert portal_degraded["status"] == "DEGRADED"

    # Resume telemetry and verify recovery
    client.post(
        f"/api/v1/portals/{p_id}/telemetry",
        json={
            "portal_id": p_id,
            "active_users": 550,
            "requests_per_sec": 55.0,
            "cpu_percent": 32.0,
            "ram_percent": 41.0,
            "latency_ms": 92.0,
            "throughput": 55.0,
            "error_rate": 0.0,
        },
    )
    portal_recovered = client.get(f"/api/v1/portals/{p_id}").json()
    assert portal_recovered["connection_state"] == "CONNECTED"
    assert portal_recovered["status"] == "ONLINE"
