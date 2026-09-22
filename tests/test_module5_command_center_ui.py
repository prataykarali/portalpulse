"""Tests for Module 5: Unified Live Resilience Command Center UI Storyboard.

Verifies:
1. Top Section: PORTALPULSE, LIVE RESILIENCE COMMAND CENTER, SYSTEM OPERATIONAL,
   CONTROL CYCLE #042, RESULT-DAY SCENARIO, 12,481 VUs.
2. Row 1: Traffic KPIs (VUs, RPS, P95, ERROR, CAPACITY).
3. Row 2: Four live graphs (VUs/RPS, p50/p95/p99, CPU/DB/Queue, error rate).
4. Row 3: Intelligence Grid (M2 FORECAST, M3 ANOMALY, M4 RCA, M5 POLICY).
5. Row 4: Actual Control Path (TRAFFIC -> M1 -> M2 -> M3 -> M4 -> M5 -> M6 -> M7 -> RECOVERING).
6. Bottom: Live Event Terminal with timestamped events.
7. CSS and JavaScript assets deliver the high-performance canvas engine and reactive terminal.
"""

import pytest
from fastapi.testclient import TestClient

from backend.app import app


@pytest.fixture
def client():
    return TestClient(app)


def test_command_center_html_storyboard(client):
    """Verify index.html contains all 5 rows of the unified command center storyboard."""
    resp = client.get("/", headers={"accept": "text/html"})
    assert resp.status_code == 200
    html = resp.text

    # Top Header & Status
    assert "PORTALPULSE" in html
    assert "LIVE RESILIENCE COMMAND CENTER" in html
    assert "SYSTEM OPERATIONAL" in html
    assert "CONTROL CYCLE" in html
    assert "RESULT-DAY SCENARIO" in html
    assert "12,481 VUs" in html

    # Row 1 — Traffic KPIs
    assert 'id="lrKpiVus"' in html
    assert 'id="lrKpiRps"' in html
    assert 'id="lrKpiP95"' in html
    assert 'id="lrKpiError"' in html
    assert 'id="lrKpiCapacity"' in html

    # Row 2 — 4 Live Graphs (Canvases)
    assert 'id="lrChartVusRps"' in html
    assert 'id="lrChartLatency"' in html
    assert 'id="lrChartResources"' in html
    assert 'id="lrChartErrors"' in html

    # Row 3 — Intelligence Grid (M2, M3, M4, M5)
    assert "M2 FORECAST" in html
    assert 'id="lrM2_5m"' in html
    assert 'id="lrM2_10m"' in html
    assert 'id="lrM2_15m"' in html
    assert 'id="lrM2_safe"' in html

    assert "M3 ANOMALY" in html
    assert 'id="lrM3_score"' in html
    assert 'id="lrM3_badge"' in html

    assert "M4 RCA" in html
    assert 'id="lrM4_db_pct"' in html
    assert 'id="lrM4_net_pct"' in html
    assert 'id="lrM4_path"' in html

    assert "M5 POLICY" in html
    assert 'id="lrM5_action"' in html
    assert 'id="lrM5_conf"' in html

    # Row 4 — Actual Control Path
    assert "Actual Control Path" in html
    assert 'id="lrNodeTraffic"' in html
    assert 'id="lrNodeM1"' in html
    assert 'id="lrNodeM2"' in html
    assert 'id="lrNodeM3"' in html
    assert 'id="lrNodeM4"' in html
    assert 'id="lrNodeM5"' in html
    assert 'id="lrNodeM6"' in html
    assert 'id="lrNodeM7"' in html
    assert 'id="lrNodeRec"' in html

    # Bottom — Live Event Terminal
    assert "LIVE EVENT TERMINAL" in html
    assert 'id="lrEventTerminal"' in html


def test_command_center_style_css(client):
    """Verify style.css includes all Module 5 responsive styles."""
    resp = client.get("/style.css")
    assert resp.status_code == 200
    css = resp.text

    assert ".lr-command-center" in css
    assert ".lr-top-header" in css
    assert ".lr-row-traffic" in css
    assert ".lr-kpi-card" in css
    assert ".lr-graphs-grid" in css
    assert ".lr-graph-card" in css
    assert ".lr-intel-grid" in css
    assert ".lr-intel-card" in css
    assert ".lr-control-path-card" in css
    assert ".lr-node" in css
    assert ".lr-terminal-card" in css
    assert ".lr-terminal-body" in css


def test_command_center_app_js_controller(client):
    """Verify app.js includes canvas chart rendering and reactive terminal controller."""
    resp = client.get("/app.js")
    assert resp.status_code == 200
    js = resp.text

    assert "LR_STATE" in js
    assert "initLRCommandCenter" in js
    assert "seedLRTerminal" in js
    assert "appendLRTerminalEntry" in js
    assert "clearTerminal" in js
    assert "drawLRChart" in js
    assert "renderAllLRCharts" in js
    assert "updateLRDom" in js
    assert "M2 capacity breach predicted" in js
    assert "SYSTEM STABILIZING" in js
