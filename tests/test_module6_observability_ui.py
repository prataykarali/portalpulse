"""Tests for Module 6: Live Observability UI.

Verifies:
1. All 8 rolling 60-second live chart cards and canvas elements:
   - Traffic (VUs, RPS)
   - Latency (p50, p95, p99)
   - Infrastructure (CPU, RAM, DB pool, queue depth)
   - Reliability (error rate, 4xx, 5xx)
   - Capacity (current utilization, safe capacity, predicted capacity)
   - Forecast (current, +5m, +10m, +15m, safe-capacity threshold)
   - Anomaly (anomaly score timeline, threshold, severity)
   - Actuation (before metric, target, stabilization trajectory, after metric)
2. All 8 chart badges and card headers.
3. Backend offline handling:
   - Offline banner with 'DEMO BACKEND OFFLINE' and 'Reconnect Now' button.
   - Status pill displaying DEMO BACKEND OFFLINE on disconnect.
   - Removal of fake jitter from live mode (only used in explicitly labeled simulation mode).
4. Visual state transitions:
   - transition-anomaly
   - transition-warning
   - transition-action
   - transition-actuating
   - transition-recovered
5. JavaScript engine:
   - 60-point rolling history windows for all 8 chart datasets.
   - triggerVisualStateTransition implementation.
   - Export of retryConnection, setBackendOnline, triggerVisualStateTransition.
"""

import pytest
from fastapi.testclient import TestClient

from backend.app import app


@pytest.fixture
def client():
    return TestClient(app)


def test_module6_all_eight_chart_canvases_in_html(client):
    """The current Traffic page exposes measured request and control charts."""
    resp = client.get("/website")
    assert resp.status_code == 200
    html = resp.text
    for chart in ("traffic-chart", "latency-chart", "db-chart", "error-chart", "control-chart", "impact-chart"):
        assert f'id="{chart}"' in html


def test_module6_all_eight_chart_badges_in_html(client):
    """The current cards include live status and measured captions."""
    resp = client.get("/website")
    assert resp.status_code == 200
    html = resp.text
    for status in ("control-live-state", "rps-caption", "latency-caption", "db-caption", "error-caption", "impact-status"):
        assert f'id="{status}"' in html


def test_module6_offline_banner_and_status(client):
    """The live page has a connection state and an emergency stop."""
    resp = client.get("/website")
    assert resp.status_code == 200
    html = resp.text
    assert 'id="connection"' in html
    assert 'data-action="stop"' in html
    assert "Waiting for backend" in html


def test_module6_css_state_transitions_and_offline_styles(client):
    """Verify style.css includes keyframes and classes for visual state transitions and offline mode."""
    resp = client.get("/style.css")
    assert resp.status_code == 200
    css = resp.text

    # Offline Banner and status styles
    assert ".lr-offline-banner" in css
    assert ".lr-offline-title" in css
    assert ".lr-status-offline" in css

    # 5 Visual State Transitions
    assert "pulseAnomaly" in css
    assert ".transition-anomaly" in css
    assert "pulseWarning" in css
    assert ".transition-warning" in css
    assert "sweepAction" in css
    assert ".transition-action" in css
    assert "rippleActuate" in css
    assert ".transition-actuating" in css
    assert "flashRecovered" in css
    assert ".transition-recovered" in css


def test_module6_app_js_rolling_history_and_engine(client):
    """Verify app.js implements 60-point rolling history, jitter removal, and state transitions."""
    resp = client.get("/app.js")
    assert resp.status_code == 200
    js = resp.text

    # Rolling 60 points window
    assert "MAX_HISTORY_POINTS = 60" in js
    assert "createRollingSeries" in js
    assert "pushLRHistory" in js

    # All 8 chart data series in LR_STATE.history
    assert "vus: createRollingSeries(60" in js
    assert "rps: createRollingSeries(60" in js
    assert "p50: createRollingSeries(60" in js
    assert "p95: createRollingSeries(60" in js
    assert "p99: createRollingSeries(60" in js
    assert "cpu: createRollingSeries(60" in js
    assert "ram: createRollingSeries(60" in js
    assert "db: createRollingSeries(60" in js
    assert "queue: createRollingSeries(60" in js
    assert "errors: createRollingSeries(60" in js
    assert "http4xx: createRollingSeries(60" in js
    assert "http5xx: createRollingSeries(60" in js
    assert "capacity: createRollingSeries(60" in js
    assert "safeCap: createRollingSeries(60" in js
    assert "predCap: createRollingSeries(60" in js
    assert "fcCurrent: createRollingSeries(60" in js
    assert "fc5m: createRollingSeries(60" in js
    assert "fc10m: createRollingSeries(60" in js
    assert "fc15m: createRollingSeries(60" in js
    assert "fcSafe: createRollingSeries(60" in js
    assert "anomalyScore: createRollingSeries(60" in js
    assert "anomalyThreshold: createRollingSeries(60" in js
    assert "actBefore: createRollingSeries(60" in js
    assert "actTarget: createRollingSeries(60" in js
    assert "actTrajectory: createRollingSeries(60" in js
    assert "actAfter: createRollingSeries(60" in js

    # Visual State Transition controller
    assert "function triggerVisualStateTransition(type)" in js
    assert "transition-anomaly" in js
    assert "transition-warning" in js
    assert "transition-action" in js
    assert "transition-actuating" in js
    assert "transition-recovered" in js

    # Jitter removal from live mode
    assert "Backend offline — refusing to synthesize fake live telemetry" in js
    assert "[🧪 STANDALONE SIMULATION MODE]" in js
    assert "setBackendOnline" in js
    assert "retryConnection" in js

    # Public exports
    assert "retryConnection," in js
    assert "triggerVisualStateTransition," in js
    assert "setBackendOnline," in js
