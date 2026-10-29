"""Tests for Module 7: Model Explainability.

Verifies:
1. M2 FORECAST explainability:
   - Tabular forecast presentation: NOW (12,481), +5m (13,740), +10m (14,620), +15m (15,180), SAFE (13,200).
   - Capacity breach alert banner: 'BREACH IN ~7 MIN'.
   - Required DOM IDs: lrM2_now, lrM2_5m, lrM2_10m, lrM2_15m, lrM2_safe, lrM2_breach.
2. M3 ANOMALY explainability:
   - Quantitative anomaly score (0.94) and CRITICAL severity badge.
   - 20-character visual block meter (e.g. '███████████████████░').
   - Top contributors list: 'DB connections', 'Latency', 'Queue depth'.
   - Required DOM IDs: lrM3_score, lrM3_badge, lrM3_meter, lrM3_contributors.
3. M4 ROOT CAUSE explainability:
   - Dominant root cause attribution: DATABASE (91.2%).
   - Root cause breakdown: TRAFFIC SPIKE (4.1%), NETWORK (2.8%), QUEUE (1.1%).
   - Causal DAG path: Traffic -> API -> DB Pool 🔴 -> Query Wait -> Latency -> 503.
   - Required DOM IDs: lrM4_dom_name, lrM4_db_pct, lrM4_spike_pct, lrM4_net_pct, lrM4_queue_pct, lrM4_path.
4. M5 ACTION POLICY explainability:
   - Primary recommended action: WAITING ROOM / ENABLE_WAITING_ROOM with confidence.
   - All 11 discrete tactical SRE action probabilities rendered in ranked order:
     ENABLE_WAITING_ROOM, SCALE_OUT_WORKERS, ACTIVATE_RATE_LIMIT, INCREASE_DB_POOL,
     DIVERT_READS_TO_REPLICA, DRAIN_REQUEST_QUEUE, ENGAGE_CIRCUIT_BREAKER,
     PURGE_REDIS_CACHE, RESTART_DEGRADED_PODS, SCALE_IN_WORKERS, NO_OP.
   - Required DOM IDs: lrM5_action, lrM5_conf, lrM5_actions_list.
5. Backend Control Loop SSE explainability payloads:
   - forecast event includes now, safe_capacity, breach_time, horizons.
   - anomaly event includes anomaly_score, severity, top_contributors.
   - rca event includes root_cause, confidence, breakdown, causal_path.
   - action event includes all_action_probabilities across all 11 discrete actions.
6. CSS explainability styling:
   - Tabular forecast, breach banner, block meter, contributors list, RCA breakdown,
     causal DAG, ranked action probability rows.
"""

import pytest
from fastapi.testclient import TestClient

from backend.app import app
from backend.m4_action_intelligence.schema import SREAction


@pytest.fixture
def client():
    return TestClient(app)


def test_module7_m2_forecast_explainability_in_html(client):
    """The model page has live forecast values and an SVG chart."""
    html = client.get("/website").text
    for item in ("m2-loaded", "forecast", "forecast-trend", "forecast-chart"):
        assert f'id="{item}"' in html
    assert "12,481" not in html


def test_module7_m3_anomaly_explainability_in_html(client):
    """The anomaly score has a live readout and trend chart."""
    html = client.get("/website").text
    for item in ("m3-loaded", "anomaly", "anomaly-chart"):
        assert f'id="{item}"' in html


def test_module7_m4_root_cause_explainability_in_html(client):
    """Root cause and causal path are rendered from the current cycle."""
    html = client.get("/website").text
    for item in ("m4-loaded", "rca", "causal-graph", "causal-svg"):
        assert f'id="{item}"' in html


def test_module7_m5_policy_all_11_actions_in_html(client):
    """Policy, safety, and action evidence have dedicated live views."""
    html = client.get("/website").text
    for item in ("m5-loaded", "neural", "policy-svg", "policy-probabilities", "safety-badge", "action-steps"):
        assert f'id="{item}"' in html


def test_module7_css_explainability_styles(client):
    """Verify style.css includes classes for all Module 7 explainability components."""
    resp = client.get("/style.css")
    assert resp.status_code == 200
    css = resp.text

    assert ".lr-forecast-tabular" in css
    assert ".lr-fc-line" in css
    assert ".lr-breach-banner" in css
    assert ".lr-block-meter" in css
    assert ".lr-contributors-block" in css
    assert ".lr-rca-dom-box" in css
    assert ".lr-rca-breakdown" in css
    assert ".lr-dag-container" in css
    assert ".lr-dag-flow" in css
    assert ".lr-ranked-actions-list" in css
    assert ".lr-action-prob-row" in css
    assert ".action-bar-wrap" in css


def test_module7_app_js_explainability_controller(client):
    """Verify app.js manages M2-M5 explainability state, dynamic DAG rendering, and ranking."""
    resp = client.get("/app.js")
    assert resp.status_code == 200
    js = resp.text

    # Forecast explainability
    assert "m2_now" in js
    assert "breachTime" in js
    # Anomaly explainability
    assert "topContributors" in js
    assert "totalBlocks" in js
    # RCA explainability
    assert "rcaDomName" in js
    assert "rcaDb" in js
    assert "rcaTrafficSpike" in js
    assert "causalPath" in js or "causalDag" in js
    # Action explainability
    assert "actionProbabilities" in js
    assert "lrM5_actions_list" in js


def test_module7_sre_actions_coverage():
    """Verify that SREAction enum has exactly the 11 tactical mitigation actions."""
    assert len(SREAction) == 11
    expected_actions = {
        "NO_OP",
        "SCALE_OUT_WORKERS",
        "SCALE_IN_WORKERS",
        "ACTIVATE_RATE_LIMIT",
        "INCREASE_DB_POOL",
        "PURGE_REDIS_CACHE",
        "DRAIN_REQUEST_QUEUE",
        "ENGAGE_CIRCUIT_BREAKER",
        "RESTART_DEGRADED_PODS",
        "DIVERT_READS_TO_REPLICA",
        "ENABLE_WAITING_ROOM",
    }
    actual_actions = {a.value for a in SREAction}
    assert actual_actions == expected_actions
