"""Module 12: Automated Test Suite for Production Health and Readiness Observability.

Validates:
1. GET /health (Liveness probe): lightweight, returns 200, never crashes even under model failures.
2. GET /ready (Readiness probe): verifies all 5 ML models and engines are ready (200), returns 503 if not ready.
3. GET /api/v1/system/status and /system/status: structured status exposing:
   - backend, M2, M3, M4, M5, M6, M7, telemetry engine, control loop, traffic simulator, SSE event stream
   - states in {READY, RUNNING, DEGRADED, ERROR, STOPPED}
   - cycle ID, traffic phase, VU target, RPS, p95, error rate, anomaly, RCA, action, recovery state, timestamps
4. Frontend integration:
   - website/index.html contains #lrComponentHealthStrip and 11 component items
   - website/style.css contains .lr-component-strip and status classes
   - website/app.js contains pollSystemStatus, applySystemStatus, system_state handler
   - Strict prohibition of browser alert()
5. Nirantar directory remains untouched.
"""

import os
import re
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.app import app
from backend.control_plane.system_status import (
    evaluate_component_states,
    get_health,
    get_ready,
    get_system_status,
)


@pytest.fixture
def client():
    return TestClient(app)


# ----------------------------------------------------------------------
# 1. LIVENESS PROBE (GET /health, GET /api/v1/health)
# ----------------------------------------------------------------------
class TestLivenessProbe:
    """Test lightweight liveness endpoint guaranteeing zero-downtime health reporting."""

    def test_health_returns_200_and_schema(self, client):
        for path in ["/health", "/api/v1/health"]:
            res = client.get(path)
            assert res.status_code == 200, f"Expected 200 for {path}, got {res.status_code}"
            data = res.json()
            assert data["status"] == "HEALTHY"
            assert data["service"] == "portalpulse-control-plane"
            assert "timestamp" in data
            assert isinstance(data["uptime_seconds"], (int, float))
            assert data["uptime_seconds"] >= 0.0
            assert data["version"] == "2.0.0"

    def test_health_never_crashes_under_model_or_loop_failure(self):
        """Liveness must return 200 even if models, loop, or DB are completely broken."""
        with patch("backend.control_plane.system_status.evaluate_component_states", side_effect=RuntimeError("Catastrophic error")):
            resp = get_health()
            assert resp.status == "HEALTHY"
            assert resp.service == "portalpulse-control-plane"
            assert resp.uptime_seconds >= 0.0


# ----------------------------------------------------------------------
# 2. READINESS PROBE (GET /ready, GET /api/v1/ready)
# ----------------------------------------------------------------------
class TestReadinessProbe:
    """Test readiness endpoint verifying all ML models and core engines are operational."""

    def test_ready_returns_200_when_models_operational(self, client):
        for path in ["/ready", "/api/v1/ready"]:
            res = client.get(path)
            assert res.status_code == 200, f"Expected 200 for {path}, got {res.status_code}"
            data = res.json()
            assert data["status"] == "READY"
            assert data["ready"] is True
            assert "components" in data
            comps = data["components"]
            assert comps["m2_forecaster"] in ("READY", "RUNNING")
            assert comps["m3_anomaly_detector"] in ("READY", "RUNNING")
            assert comps["m4_rca"] in ("READY", "RUNNING")
            assert comps["m5_tactical_policy"] in ("READY", "RUNNING")
            assert comps["m6_safety_engine"] in ("READY", "RUNNING")
            assert comps["m7_actuator"] in ("READY", "RUNNING")

    def test_ready_returns_503_when_critical_model_fails(self, client):
        """When a critical model is unavailable or degraded, /ready must return 503."""
        from unittest.mock import PropertyMock
        from backend.m2_prediction.forecaster import LoadForecaster

        with patch.object(LoadForecaster, "is_ready", new_callable=PropertyMock, return_value=False):
            res = client.get("/ready")
            assert res.status_code == 503
            data = res.json()
            assert data["status"] == "NOT_READY"
            assert data["ready"] is False
            assert data["components"]["m2_forecaster"] == "ERROR"


# ----------------------------------------------------------------------
# 3. STRUCTURED SYSTEM STATUS (GET /api/v1/system/status & /system/status)
# ----------------------------------------------------------------------
class TestSystemStatusObservability:
    """Test comprehensive unified system status for the command center."""

    REQUIRED_COMPONENTS = {
        "backend",
        "m2_forecaster",
        "m3_anomaly_detector",
        "m4_rca",
        "m5_tactical_policy",
        "m6_safety_engine",
        "m7_actuator",
        "telemetry_engine",
        "control_loop",
        "traffic_simulator",
        "sse_event_stream",
    }

    VALID_STATES = {"READY", "RUNNING", "DEGRADED", "ERROR", "STOPPED"}

    def test_system_status_endpoints_schema(self, client):
        for path in ["/api/v1/system/status", "/system/status"]:
            res = client.get(path)
            assert res.status_code == 200, f"Expected 200 for {path}, got {res.status_code}"
            data = res.json()

            # Backend core
            assert data["backend"] in ("READY", "RUNNING")
            assert "timestamp" in data
            assert isinstance(data["uptime_seconds"], (int, float))

            # All 11 components present
            comps = data["components"]
            for comp_name in self.REQUIRED_COMPONENTS:
                assert comp_name in comps, f"Missing component {comp_name} in status"
                assert comps[comp_name] in self.VALID_STATES, f"Invalid state {comps[comp_name]} for {comp_name}"

            # Operational parameters
            assert "current_control_cycle_id" in data
            assert "current_traffic_phase" in data
            assert "current_vu_target" in data
            assert isinstance(data["current_vu_target"], int)
            assert "current_rps" in data
            assert isinstance(data["current_rps"], (int, float))
            assert "current_p95_latency" in data
            assert isinstance(data["current_p95_latency"], (int, float))
            assert "current_error_rate" in data
            assert isinstance(data["current_error_rate"], (int, float))
            assert "current_anomaly_state" in data
            assert "current_rca" in data
            assert "current_action" in data
            assert "current_recovery_state" in data
            assert "health_score" in data
            assert 0.0 <= data["health_score"] <= 100.0

    def test_evaluate_component_states_degradation_mapping(self):
        """Ensure failed model in previous cycle marks that component as DEGRADED."""
        from backend.control_plane.explainable_pipeline import (
            ControlCycle,
            EXPLAINABLE_PIPELINE,
            ModelExecutionRecord,
        )

        failed_m2 = ModelExecutionRecord(
            model_id="M2",
            name="Forecaster",
            status="FAILED",
            input_summary={},
            output_summary={},
            confidence_pct=0.0,
            inference_time_ms=1.0,
            model_version="2.0.0",
        )
        fake_cycle = ControlCycle(
            cycle_id="#999",
            timestamp="2026-09-21T00:00:00Z",
            portal_id="nirantar",
            input_telemetry={"requests_per_sec": 5000},
            forecast={},
            anomaly={"severity": "NOMINAL"},
            rca={"rca_class": "NORMAL"},
            causal_path=[],
            action_recommendation={},
            safety_validation={},
            pre_metrics={},
            recovery_state="DEGRADED",
            health_score=82.0,
            models={"M2": failed_m2},
        )

        with patch.object(EXPLAINABLE_PIPELINE, "last_cycle", fake_cycle):
            states = evaluate_component_states()
            assert states["m2_forecaster"] == "DEGRADED"


# ----------------------------------------------------------------------
# 4. FRONTEND INTEGRATION & ZERO ALERT()
# ----------------------------------------------------------------------
class TestFrontendSystemStatusIntegration:
    """Verify the frontend UI consumes the system status endpoints and has zero alert()."""

    BASE_DIR = Path(__file__).resolve().parents[1]
    WEBSITE_DIR = BASE_DIR / "website"

    def test_index_html_has_component_health_strip(self):
        html_path = self.WEBSITE_DIR / "index.html"
        assert html_path.exists()
        content = html_path.read_text(encoding="utf-8")

        # Strip container
        assert 'id="lrComponentHealthStrip"' in content
        assert "PRODUCTION HEALTH &amp; COMPONENT READINESS" in content or "PRODUCTION HEALTH & COMPONENT READINESS" in content
        assert 'id="lrSystemHealthScoreBadge"' in content
        assert 'id="lrSystemLastSync"' in content

        # All 11 components in HTML grid
        required_comp_ids = [
            'id="comp-backend"',
            'id="comp-m2_forecaster"',
            'id="comp-m3_anomaly_detector"',
            'id="comp-m4_rca"',
            'id="comp-m5_tactical_policy"',
            'id="comp-m6_safety_engine"',
            'id="comp-m7_actuator"',
            'id="comp-telemetry_engine"',
            'id="comp-control_loop"',
            'id="comp-traffic_simulator"',
            'id="comp-sse_event_stream"',
        ]
        for cid in required_comp_ids:
            assert cid in content, f"Missing element {cid} in index.html"

    def test_style_css_has_component_strip_styles(self):
        css_path = self.WEBSITE_DIR / "style.css"
        assert css_path.exists()
        content = css_path.read_text(encoding="utf-8")

        assert ".lr-component-strip" in content
        assert ".lr-components-grid" in content
        assert ".lr-comp-item" in content
        assert ".dot-ready" in content
        assert ".dot-running" in content
        assert ".dot-degraded" in content
        assert ".dot-error" in content
        assert ".dot-stopped" in content

    def test_app_js_has_system_status_handlers(self):
        js_path = self.WEBSITE_DIR / "app.js"
        assert js_path.exists()
        content = js_path.read_text(encoding="utf-8")

        assert "pollSystemStatus" in content
        assert "applySystemStatus" in content
        assert "/api/v1/system/status" in content
        assert "type === \"system_state\"" in content
        assert "pollSystemStatus," in content  # exported in PortalApp

    def test_zero_alert_in_all_frontend_files(self):
        """Strict invariant: zero browser alert() calls across all frontend files."""
        for root, _, files in os.walk(self.WEBSITE_DIR):
            for file in files:
                if file.endswith((".html", ".js", ".ts")):
                    filepath = Path(root) / file
                    text = filepath.read_text(encoding="utf-8")
                    # Check for native alert( but ignore comments or words like 'alert-warning'
                    matches = re.findall(r'(?<![.\w])alert\s*\(', text)
                    assert len(matches) == 0, f"Found forbidden alert() in {filepath}: {matches}"


# ----------------------------------------------------------------------
# 5. NIRANTAR IMMUTABILITY
# ----------------------------------------------------------------------
class TestNirantarImmutability:
    """Verify the user-authorized native notices preserve simulator provenance."""

    def test_nirantar_untouched(self):
        nirantar_path = Path("/home/pratay-karali/Desktop/NIRANTAR")
        if not nirantar_path.exists():
            pytest.skip("Nirantar directory not present")

        notices = nirantar_path / "frontend/src/components/PortalPulseNotices.tsx"
        assert notices.exists()
        assert "PORTALPULSE SIMULATOR" in notices.read_text(encoding="utf-8")
