"""Tests for Portal Adapter Layer and Environment Awareness (PRD-02 & PRD-03 §1.2)."""

import pytest
from backend.control_plane.portal_adapter import get_portal_adapter, NirantarAdapter, IEMCRPAdapter
from portalpulse_sdk.schema import UniversalTelemetry


def test_portal_adapter_discovery():
    nir_adapter = get_portal_adapter("nirantar")
    assert isinstance(nir_adapter, NirantarAdapter)
    assert nir_adapter.portal_id == "nirantar"
    assert nir_adapter.get_actuator_environment() in ["LOCAL_PROCESS", "DOCKER_COMPOSE", "KUBERNETES"]

    iemcrp_adapter = get_portal_adapter("college_portal")
    assert isinstance(iemcrp_adapter, IEMCRPAdapter)
    assert iemcrp_adapter.portal_id == "college_portal"
    assert iemcrp_adapter.get_actuator_environment() == "LOCAL_PROCESS"


def test_portal_telemetry_fetch():
    nir_adapter = get_portal_adapter("nirantar")
    tel = nir_adapter.get_telemetry()
    assert isinstance(tel, UniversalTelemetry)
    assert tel.portal_id == "nirantar"
    assert tel.cpu_percent >= 0.0

    iemcrp_adapter = get_portal_adapter("college_portal")
    tel_iemcrp = iemcrp_adapter.get_telemetry()
    assert tel_iemcrp.portal_id == "college_portal"
    assert tel_iemcrp.db_connections <= 100.0  # Must obey percentage constraint


def test_portal_action_execution_and_rollback():
    iemcrp_adapter = get_portal_adapter("college_portal")
    res = iemcrp_adapter.execute_action("STATIC_FALLBACK_DIVERT", {"divert_pct": 50})
    assert res.status == "SUCCESS"
    assert "divert" in res.message.lower()

    # Rollback
    rb_res = iemcrp_adapter.rollback_action("STATIC_FALLBACK_DIVERT", res.rollback_parameters)
    assert rb_res.status == "SUCCESS"
    assert "restored" in rb_res.message.lower() or "rolled back" in rb_res.message.lower()


def test_portal_verification_delta():
    nir_adapter = get_portal_adapter("nirantar")
    before = UniversalTelemetry(
        portal_id="nirantar",
        active_users=3000,
        requests_per_sec=400.0,
        throughput=390.0,
        latency_ms=850.0,
        p95_latency_ms=900.0,
        error_rate=0.08,
        cpu_percent=92.0,
        ram_percent=85.0,
    )
    after = UniversalTelemetry(
        portal_id="nirantar",
        active_users=3000,
        requests_per_sec=380.0,
        throughput=380.0,
        latency_ms=280.0,
        p95_latency_ms=310.0,
        error_rate=0.001,
        cpu_percent=60.0,
        ram_percent=65.0,
    )

    report = nir_adapter.verify_action(before, after)
    assert report["effective"] is True
    assert report["latency_improvement_pct"] > 60.0
    assert report["error_reduction_pct"] > 90.0
