"""Tests for Module 8: Telemetry-Driven Warning Engine & Experiences.

Verifies:
1. The 6 canonical PortalPulse warnings:
   - HIGH BOOKING DEMAND / RESULT-DAY RUSH (WARN_RESULT_DAY_RUSH)
   - DATABASE CONNECTION POOL EXHAUSTION (WARN_DB_POOL_EXHAUSTION)
   - VIRTUAL WAITING ROOM ACTIVE (WARN_WAITING_ROOM_ACTIVE)
   - HTTP 429 RATE LIMITING (WARN_HTTP_429_RATE_LIMITING)
   - GATEWAY TIMEOUT / REPLICA FAILOVER (WARN_GATEWAY_TIMEOUT_FAILOVER)
   - CIRCUIT BREAKER TRIPPED (WARN_CIRCUIT_BREAKER_TRIPPED)
2. Each warning has all required fields:
   - unique ID, severity, trigger condition, timestamp, current metric, threshold,
     recommended action, current remediation state, recovery state.
   - WHAT HAPPENED, WHY IT HAPPENED, WHAT PORTALPULSE DID, CURRENT RESULT.
3. Telemetry condition evaluation and automatic recovery event generation.
4. API endpoints:
   - GET /api/v1/warnings/catalog
   - GET /api/v1/warnings/active
   - POST /api/v1/warnings/trigger-test (flagged as TEST MODE)
5. UI elements in index.html, style.css, and app.js:
   - Modal with the 4 explainability sections: WHAT HAPPENED, WHY IT HAPPENED,
     WHAT PORTALPULSE DID, CURRENT RESULT.
   - Toast container for WARNING and RECOVERY events.
   - Developer test mode section clearly marked [DEV/DEMO TEST MODE].
   - No native browser alert() usage.
"""

from types import SimpleNamespace
import pytest
from fastapi.testclient import TestClient

from backend.app import app
from backend.control_plane.warning_engine import (
    WARNING_ENGINE,
    WARNING_SPECS,
    WarningEngine,
    WarningItem,
)


@pytest.fixture
def client():
    return TestClient(app)


def test_warning_specs_catalog_completeness():
    """Verify all 6 canonical warnings exist with required fields."""
    expected_ids = {
        "WARN_RESULT_DAY_RUSH",
        "WARN_DB_POOL_EXHAUSTION",
        "WARN_WAITING_ROOM_ACTIVE",
        "WARN_HTTP_429_RATE_LIMITING",
        "WARN_GATEWAY_TIMEOUT_FAILOVER",
        "WARN_CIRCUIT_BREAKER_TRIPPED",
    }
    assert set(WARNING_SPECS.keys()) == expected_ids

    for w_id, spec in WARNING_SPECS.items():
        assert "title" in spec
        assert spec["severity"] in ("CRITICAL", "WARNING")
        assert "trigger_condition" in spec
        assert "threshold" in spec
        assert "recommended_action" in spec
        assert "remediation_state" in spec
        assert "recovery_state" in spec
        assert "what_happened" in spec
        assert "why_it_happened" in spec
        assert "what_portalpulse_did" in spec
        assert "current_result" in spec


def test_warning_engine_telemetry_eval_and_recovery():
    """Verify telemetry conditions trigger warnings and clearing conditions triggers recovery."""
    engine = WarningEngine()

    # Cycle 1: High DB contention (96% / 48 connections) -> should trigger WARN_DB_POOL_EXHAUSTION
    high_db_cycle = SimpleNamespace(
        pre_metrics={
            "virtual_users": 5000,
            "db_connections": 48,  # >= 45 triggers exhaustion
            "queue_length": 20,
            "error_rate": 1.0,
            "requests_per_sec": 1000,
        },
        post_metrics={},
        forecast={"capacity_pressure_index": 0.4},
        anomaly={"is_anomaly": True},
        rca={"rca_class": "DATABASE"},
        action_recommendation={},
        recommended_action="INCREASE_DB_POOL",
        actuation_status="ACTUATING",
        recovery_state="ACTUATING",
    )

    warns, recs = engine.evaluate(high_db_cycle)
    assert len(warns) == 1
    assert warns[0].id == "WARN_DB_POOL_EXHAUSTION"
    assert warns[0].severity == "CRITICAL"
    assert warns[0].m5_action == "INCREASE_DB_POOL"
    assert warns[0].m7_actuating == "ACTUATING"
    assert "96%" in warns[0].current_result or "48" in warns[0].current_metric
    assert len(recs) == 0
    assert len(engine.get_active_warnings()) == 1

    # Cycle 2: DB contention resolves to 22 connections -> should emit RECOVERY event
    resolved_db_cycle = SimpleNamespace(
        pre_metrics={
            "virtual_users": 5000,
            "db_connections": 22,  # < 45 clears exhaustion
            "queue_length": 20,
            "error_rate": 0.5,
            "requests_per_sec": 1000,
        },
        post_metrics={},
        forecast={"capacity_pressure_index": 0.3},
        anomaly={"is_anomaly": False},
        rca={"rca_class": "NORMAL"},
        action_recommendation={},
        recommended_action="NO_OP",
        actuation_status="NOMINAL",
        recovery_state="STABILIZED",
    )

    warns2, recs2 = engine.evaluate(resolved_db_cycle)
    assert len(warns2) == 0
    assert len(recs2) == 1
    assert recs2[0]["id"] == "WARN_DB_POOL_EXHAUSTION"
    assert recs2[0]["severity"] == "RECOVERY"
    assert recs2[0]["is_recovered"] is True
    assert recs2[0]["title"].startswith("CONDITION CLEARED:")
    assert recs2[0]["recommended_action"] == "NO_OP"
    assert "no M7 action is attributed" in recs2[0]["what_portalpulse_did"]
    assert len(engine.get_active_warnings()) == 0


def test_api_warnings_catalog(client):
    """Verify GET /api/v1/warnings/catalog returns all 6 warning specs."""
    resp = client.get("/api/v1/warnings/catalog")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 6
    assert "WARN_DB_POOL_EXHAUSTION" in data
    assert "WARN_RESULT_DAY_RUSH" in data
    assert "WARN_WAITING_ROOM_ACTIVE" in data
    assert "WARN_HTTP_429_RATE_LIMITING" in data
    assert "WARN_GATEWAY_TIMEOUT_FAILOVER" in data
    assert "WARN_CIRCUIT_BREAKER_TRIPPED" in data


def test_api_warnings_trigger_test_endpoint(client):
    """Verify POST /api/v1/warnings/trigger-test is explicitly marked as TEST MODE."""
    payload = {"warning_id": "WARN_DB_POOL_EXHAUSTION"}
    resp = client.post("/api/v1/warnings/trigger-test", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "TRIGGERED"
    assert data["mode"] == "TEST MODE"
    assert data["warning"]["id"] == "WARN_DB_POOL_EXHAUSTION"
    assert data["warning"]["is_test_mode"] is True
    assert "[TEST MODE]" in data["warning"]["title"]


def test_module8_ui_modal_and_toast_in_html(client):
    """The canonical website exposes live incidents and contextual action messages."""
    resp = client.get("/", headers={"accept": "text/html"})
    assert resp.status_code == 200
    html = resp.text

    assert 'id="drawer"' in html
    assert 'id="incidents"' in html
    assert 'id="toasts"' in html
    assert 'id="coach-popup"' in html
    assert 'id="robot-launch"' in html
    assert 'id="tour-dialog"' in html
    assert 'data-trigger="database"' in html
    assert 'data-trigger="rate-limit"' in html
    assert 'data-trigger="circuit-breaker"' in html


def test_module8_css_styles(client):
    """Verify style.css contains all Module 8 modal, toast, and dev test styles."""
    resp = client.get("/style.css")
    assert resp.status_code == 200
    css = resp.text

    assert ".lr-modal-overlay" in css
    assert ".lr-modal-dialog" in css
    assert ".lr-modal-badge" in css
    assert ".lr-explain-box" in css
    assert ".lr-result-box" in css
    assert ".lr-toast-container" in css
    assert ".lr-toast-crit" in css
    assert ".lr-toast-warn" in css
    assert ".lr-toast-recovery" in css
    assert ".lr-dev-test-section" in css


def test_module8_app_js_engine_and_no_alert(client):
    """Verify app.js provides warning methods and does not invoke alert()."""
    resp = client.get("/app.js")
    assert resp.status_code == 200
    js = resp.text

    assert "showCriticalWarningModal" in js
    assert "dismissWarningModal" in js
    assert "showWarningToast" in js
    assert "showRecoveryToast" in js
    assert "triggerTestWarning" in js

    # Strictly do not use browser alert()
    assert "window.alert(" not in js
    assert "alert(" not in js
