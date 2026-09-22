"""Tests for Telemetry Provenance, Health Scoring, and User Impact (PRD-02 & PRD-03 §2)."""

import pytest
from backend.control_plane.provenance import (
    ProvenanceTag,
    TaggedMetric,
    tag_metric,
    validate_provenance,
)
from backend.control_plane.health_scoring import (
    compute_portal_health_score,
    compute_user_impact,
)
from portalpulse_sdk.schema import UniversalTelemetry


def test_provenance_tagging():
    m = tag_metric(412.5, ProvenanceTag.LIVE_LOCUST, "Locust worker thread aggregate")
    assert m.value == 412.5
    assert m.provenance == "LIVE_LOCUST"
    assert validate_provenance(m) is True


def test_compute_portal_health_score_nominal():
    tel = UniversalTelemetry(
        portal_id="nirantar",
        active_users=800,
        requests_per_sec=150.0,
        throughput=150.0,
        latency_ms=35.0,
        p95_latency_ms=55.0,
        error_rate=0.0,
        cpu_percent=25.0,
        ram_percent=35.0,
        db_connections=20.0,
    )
    res = compute_portal_health_score(tel, capacity_pci=0.30)
    assert res["score"] >= 85.0
    assert res["status"] == "EXCELLENT"
    assert res["color"] == "#10B981"


def test_compute_portal_health_score_critical():
    tel = UniversalTelemetry(
        portal_id="college_portal",
        active_users=4500,
        requests_per_sec=280.0,
        throughput=240.0,
        latency_ms=1200.0,
        p95_latency_ms=1850.0,
        error_rate=0.15,
        cpu_percent=94.0,
        ram_percent=88.0,
        db_connections=98.0,
    )
    res = compute_portal_health_score(tel, capacity_pci=1.1)
    assert res["score"] < 50.0
    assert res["status"] == "CRITICAL"
    assert res["color"] == "#EF4444"


def test_compute_user_impact():
    tel = UniversalTelemetry(
        portal_id="nirantar",
        active_users=5000,
        requests_per_sec=500.0,
        throughput=480.0,
        latency_ms=900.0,
        p95_latency_ms=1400.0,
        error_rate=0.04,
        cpu_percent=82.0,
        ram_percent=75.0,
        active_sessions=5000,
    )
    impact = compute_user_impact(tel, waiting_room_queue=250, active_sessions=5000, before_affected_users=3000)
    assert impact["users_affected"] > 0
    assert impact["est_waiting_time_sec"] > 0.0
    assert impact["protected_users"] > 0
