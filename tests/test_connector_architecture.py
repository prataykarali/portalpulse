"""Unit and Integration Tests for PortalPulse Pluggable Connector Architecture.

Verifies:
1. Universal Telemetry schema conversion and validation.
2. Capability discovery and Action Masking (preventing unpermitted actions like DB replicas on constrained portals).
3. Dynamic NetworkX dependency graph generation from custom topology specs.
4. Reference connectors (Nirantar, College Portal, eCommerce).
5. Pluggable SDK Agent (PortalPulseAgent) telemetry building and action dispatching.
6. Multi-Portal Control Plane FastAPI endpoints.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.app import app
from backend.connectors.college_portal import CollegePortalConnector
from backend.connectors.ecommerce import ECommerceConnector
from backend.connectors.nirantar import NirantarConnector
from backend.control_plane.action_masker import ACTION_MASKER
from backend.control_plane.dynamic_graph import DynamicTopologyDAG
from backend.control_plane.registry import PortalRegistry
from backend.control_plane.schema import (
    ActionMask,
    MaskedRecommendation,
    PortalRegistrationRequest,
)
from backend.m4_action_intelligence.schema import SREAction
from portalpulse_sdk.agent import PortalPulseAgent
from portalpulse_sdk.schema import (
    ActionCommand,
    ActionResult,
    DependencyGraphSpec,
    PortalCapabilities,
    UniversalTelemetry,
)

client = TestClient(app)


# =========================================================================
# 1. Universal Telemetry & SDK Agent Tests
# =========================================================================


def test_universal_telemetry_schema_validation() -> None:
    """Verify UniversalTelemetry field constraints and default values."""
    tel = UniversalTelemetry(
        portal_id="demo_portal",
        active_users=5400,
        requests_per_sec=820.5,
        cpu_percent=64.2,
        ram_percent=71.0,
        latency_ms=320.0,
        throughput=805.0,
        error_rate=0.003,
        db_latency_ms=45.0,
        db_connections=62.0,
        queue_length=15,
        service_instances=4,
    )
    assert tel.portal_id == "demo_portal"
    assert tel.active_users == 5400
    assert tel.cpu_percent == 64.2
    assert tel.error_rate == 0.003
    assert tel.network_in_mb == 10.0


def test_portalpulse_agent_telemetry_factory_and_handlers() -> None:
    """Verify client SDK agent telemetry builder and local action dispatching."""
    agent = PortalPulseAgent(
        portal_id="custom_portal",
        portal_name="Custom Web Application",
    )

    # 1. Telemetry creation
    tel = agent.build_telemetry(
        active_users=1200,
        requests_per_sec=150.0,
        cpu_percent=45.0,
        ram_percent=50.0,
        latency_ms=110.0,
        throughput=149.0,
        error_rate=0.001,
    )
    assert tel.portal_id == "custom_portal"
    assert tel.active_users == 1200

    # 2. Register local action callback
    scale_called = False

    def handle_scale(params: dict[str, object]) -> ActionResult:
        nonlocal scale_called
        scale_called = True
        return ActionResult(
            action_id="act-101",
            portal_id="custom_portal",
            success=True,
            message="Scaled custom application pods.",
        )

    agent.register_action_handler("SCALE_OUT_WORKERS", handle_scale)

    cmd = ActionCommand(
        action_id="act-101",
        portal_id="custom_portal",
        action_type="SCALE_OUT_WORKERS",
        parameters={"delta": 2},
    )
    res = agent.dispatch_local_action(cmd)
    assert res.success is True
    assert scale_called is True

    # 3. Unregistered action
    unregistered_cmd = ActionCommand(
        action_id="act-102",
        portal_id="custom_portal",
        action_type="PURGE_REDIS_CACHE",
    )
    unreg_res = agent.dispatch_local_action(unregistered_cmd)
    assert unreg_res.success is False
    assert "No local handler" in unreg_res.message


# =========================================================================
# 2. Reference Connectors Tests
# =========================================================================


def test_nirantar_connector_capabilities_and_actions() -> None:
    """Nirantar should expose full capabilities and support enterprise actions."""
    conn = NirantarConnector()
    caps = conn.get_capabilities()
    assert caps.horizontal_scaling is True
    assert caps.database_replica is True
    assert caps.caching is True

    deps = conn.get_dependencies()
    assert "postgresql_db" in deps.nodes
    assert ("backend", "postgresql_db") in deps.edges or ("worker_backend", "postgresql_db") in deps.edges

    health = conn.get_health()
    assert health["status"] == "HEALTHY"

    # Test scale out
    scale_cmd = ActionCommand(
        action_id="cmd-1",
        portal_id="nirantar",
        action_type="SCALE_OUT_WORKERS",
        parameters={"delta_instances": 4},
    )
    res = conn.execute_action(scale_cmd)
    assert res.success is True
    assert conn.pods >= 12


def test_college_portal_connector_constrained_capabilities() -> None:
    """College portal must reject unsupported replica and cache calls."""
    conn = CollegePortalConnector()
    caps = conn.get_capabilities()
    assert caps.horizontal_scaling is True
    assert caps.database_replica is False  # Monolithic DB
    assert caps.caching is False  # No Redis

    # Execution of unpermitted replica diversion should be cleanly rejected
    replica_cmd = ActionCommand(
        action_id="cmd-2",
        portal_id="college_portal",
        action_type="DIVERT_READS_TO_REPLICA",
    )
    res_replica = conn.execute_action(replica_cmd)
    assert res_replica.success is False
    assert "REJECTED" in res_replica.message

    # Execution of permitted waiting room
    wait_cmd = ActionCommand(
        action_id="cmd-3",
        portal_id="college_portal",
        action_type="ENABLE_WAITING_ROOM",
    )
    res_wait = conn.execute_action(wait_cmd)
    assert res_wait.success is True
    assert conn.waiting_room_active is True


def test_ecommerce_connector() -> None:
    """ECommerce connector supports feature flags and circuit breakers."""
    conn = ECommerceConnector()
    caps = conn.get_capabilities()
    assert caps.feature_flags is True
    assert caps.circuit_breaker is True

    cb_cmd = ActionCommand(
        action_id="cmd-4",
        portal_id="ecommerce",
        action_type="ENGAGE_CIRCUIT_BREAKER",
    )
    res = conn.execute_action(cb_cmd)
    assert res.success is True
    assert conn.circuit_open is True


# =========================================================================
# 3. Action Masking & Dynamic DAG Tests
# =========================================================================


def test_action_masker_blocks_unsupported_actions() -> None:
    """Verify ActionMasker zeros out unsupported actions and re-normalizes probabilities."""
    # Constrained capabilities: no replica, no cache
    caps = PortalCapabilities(
        horizontal_scaling=True,
        database_replica=False,
        caching=False,
        rate_limiting=True,
    )

    mask: ActionMask = ACTION_MASKER.get_action_mask(caps, "test_college")
    assert SREAction.DIVERT_READS_TO_REPLICA.value in mask.masked_actions
    assert SREAction.PURGE_REDIS_CACHE.value in mask.masked_actions
    assert SREAction.SCALE_OUT_WORKERS.value in mask.permitted_actions
    assert SREAction.NO_OP.value in mask.permitted_actions

    # Simulate neural policy output with high probability on DIVERT_READS_TO_REPLICA
    raw_probs = {
        SREAction.DIVERT_READS_TO_REPLICA.value: 0.70,
        SREAction.SCALE_OUT_WORKERS.value: 0.20,
        SREAction.NO_OP.value: 0.10,
    }

    masked_rec: MaskedRecommendation = ACTION_MASKER.apply_mask("test_college", raw_probs, caps)
    assert masked_rec.was_masked is True
    assert masked_rec.raw_action == SREAction.DIVERT_READS_TO_REPLICA.value
    # Diverted to highest allowed action: SCALE_OUT_WORKERS
    assert masked_rec.effective_action == SREAction.SCALE_OUT_WORKERS.value
    # Assert masked probability is strictly 0.0
    assert masked_rec.effective_probabilities[SREAction.DIVERT_READS_TO_REPLICA.value] == 0.0
    # Assert probabilities sum to ~1.0
    assert sum(masked_rec.effective_probabilities.values()) == pytest.approx(1.0, abs=1e-3)


def test_dynamic_topology_dag_custom_graph() -> None:
    """Verify NetworkX DAG construction and causal tracing on arbitrary custom topologies."""
    # Custom 4-tier mobile app architecture
    spec = DependencyGraphSpec(
        nodes=["mobile_app", "kong_api_gateway", "catalog_service", "document_db"],
        edges=[
            ("mobile_app", "kong_api_gateway"),
            ("kong_api_gateway", "catalog_service"),
            ("catalog_service", "document_db"),
        ],
        entrypoint_node="mobile_app",
        storage_nodes=["document_db"],
    )

    dag = DynamicTopologyDAG(spec)
    assert dag.node_depths["mobile_app"] == 0
    assert dag.node_depths["kong_api_gateway"] == 1
    assert dag.node_depths["catalog_service"] == 2
    assert dag.node_depths["document_db"] == 3

    # Anomaly on document_db (depth 3) and catalog_service (depth 2)
    scores = {
        "mobile_app": 0.10,
        "kong_api_gateway": 0.40,
        "catalog_service": 0.75,
        "document_db": 0.90,
    }
    root, path, conf = dag.trace_root_cause(scores, anomaly_threshold=0.50)
    assert root == "document_db"
    assert path == ["mobile_app", "kong_api_gateway", "catalog_service", "document_db"]
    assert conf == 0.90


# =========================================================================
# 4. Multi-Portal Registry & Control Plane Coordinator Tests
# =========================================================================


def test_portal_registry_registration_and_isolation() -> None:
    """Verify registration, telemetry isolation, and capability lookup."""
    registry = PortalRegistry()

    req = PortalRegistrationRequest(
        portal_id="hospital_erp",
        portal_name="National Hospital Emergency ERP",
        connector_type="python_sdk",
        capabilities=PortalCapabilities(horizontal_scaling=True, database_replica=False),
    )
    resp = registry.register_portal(req)
    assert resp.status in ("REGISTERED", "CONNECTED")
    assert resp.portal_id == "hospital_erp"

    # Verify portal is stored
    info = registry.get_portal("hospital_erp")
    assert info is not None
    assert info.portal_name == "National Hospital Emergency ERP"

    # Ingest telemetry for hospital_erp
    tel = UniversalTelemetry(
        portal_id="hospital_erp",
        active_users=3200,
        requests_per_sec=450.0,
        cpu_percent=55.0,
        ram_percent=60.0,
        latency_ms=180.0,
        throughput=448.0,
        error_rate=0.002,
    )
    registry.record_telemetry(tel)
    latest = registry.get_latest_telemetry("hospital_erp")
    assert latest is not None
    assert latest.active_users == 3200


# =========================================================================
# 5. FastAPI Endpoints for Multi-Portal Control Plane
# =========================================================================


def test_api_list_portals() -> None:
    """GET /api/v1/portals lists attached reference connectors."""
    res = client.get("/api/v1/portals")
    assert res.status_code == 200
    data = res.json()
    assert data["total_portals"] >= 2
    portal_ids = [p["portal_id"] for p in data["portals"]]
    assert "nirantar" in portal_ids
    assert "college_portal" in portal_ids


def test_api_get_portal_capabilities_and_dependencies() -> None:
    """Inspect capability and dependency discovery endpoints."""
    # 1. Nirantar capabilities
    res_nirantar = client.get("/api/v1/portals/nirantar/capabilities")
    assert res_nirantar.status_code == 200
    nir_caps = res_nirantar.json()
    assert nir_caps["horizontal_scaling"] is True
    assert nir_caps["database_replica"] is True

    # 2. College portal capabilities
    res_college = client.get("/api/v1/portals/college_portal/capabilities")
    assert res_college.status_code == 200
    col_caps = res_college.json()
    assert col_caps["database_replica"] is False
    assert col_caps["caching"] is False

    # 3. Dynamic dependency graph
    res_deps = client.get("/api/v1/portals/college_portal/dependencies")
    assert res_deps.status_code == 200
    col_deps = res_deps.json()
    assert "nodes" in col_deps
    assert "edges" in col_deps


def test_api_portal_telemetry_ingest_and_live() -> None:
    """POST telemetry and GET live telemetry."""
    tel_payload = {
        "portal_id": "nirantar",
        "active_users": 34100,
        "requests_per_sec": 4850.0,
        "cpu_percent": 74.5,
        "ram_percent": 71.0,
        "latency_ms": 310.0,
        "throughput": 4820.0,
        "error_rate": 0.003,
        "db_latency_ms": 32.0,
        "db_connections": 58.0,
        "queue_length": 25,
        "service_instances": 8,
    }
    res_post = client.post("/api/v1/portals/nirantar/telemetry", json=tel_payload)
    assert res_post.status_code == 200

    res_get = client.get("/api/v1/portals/nirantar/telemetry/live")
    assert res_get.status_code == 200
    live_data = res_get.json()
    assert live_data["active_users"] == 34100
    assert live_data["requests_per_sec"] == 4850.0


def test_api_prescribe_and_mask_action_college_portal() -> None:
    """POST /api/v1/portals/college_portal/actions/prescribe-and-mask."""
    # Under high DB saturation, raw model might suggest DIVERT_READS_TO_REPLICA,
    # but college portal mask must override it!
    res = client.post("/api/v1/portals/college_portal/actions/prescribe-and-mask")
    assert res.status_code == 200
    data = res.json()
    assert data["portal_id"] == "college_portal"
    assert "effective_action" in data
    # DIVERT_READS_TO_REPLICA is masked out on college portal
    assert data["effective_probabilities"]["DIVERT_READS_TO_REPLICA"] == 0.0
    assert data["effective_probabilities"]["PURGE_REDIS_CACHE"] == 0.0


def test_api_dispatch_action() -> None:
    """POST /api/v1/portals/nirantar/actions/dispatch."""
    cmd = {
        "action_id": "cmd-test-999",
        "portal_id": "nirantar",
        "action_type": "SCALE_OUT_WORKERS",
        "parameters": {"delta_instances": 2},
    }
    res = client.post("/api/v1/portals/nirantar/actions/dispatch", json=cmd)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert "Scaled out Nirantar pods" in data["message"]
