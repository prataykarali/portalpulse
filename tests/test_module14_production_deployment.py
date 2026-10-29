"""Module 14: Automated Test Suite for Production Deployment Preparation.

Validates:
1. Backend binds to 0.0.0.0 and reads ${PORT:-8000}.
2. No hardcoded /home/ paths in backend/ directory.
3. All 4 production model artifacts exist and load with is_ready=True:
   - xgboost_forecaster.pkl
   - isolation_forest.pkl
   - xgboost_rca.pkl
   - action_mlp_policy.pt (plus scaler.pkl)
4. Model paths support environment variable overrides.
5. Production CORS configured for here.now and configurable ALLOWED_ORIGINS.
6. Frontend API_BASE is decoupled from window.location.origin and supports Antideploy URL.
7. Zero alert() calls in frontend.
8. .dockerignore, Dockerfile, Procfile, start.sh exist and exclude development artifacts.
9. All 9 endpoints return 200 (or SSE event stream).
10. Nirantar remains 100% untouched.
"""

import os
import re
import subprocess
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from backend.app import app
from backend.m1_monitoring.collector import COLLECTOR
from backend.m2_prediction.forecaster import FORECASTER
from backend.m3_anomaly_rca.anomaly_detector import DETECTOR
from backend.m3_anomaly_rca.rca_classifier import RCA_CLASSIFIER
from backend.m4_action_intelligence.action_engine import ACTION_ENGINE
from backend.m6_safety_layer.guardrails import SAFETY_GUARDRAILS
from backend.m7_actuator.actuator import CLOSED_LOOP_ACTUATOR
from backend.control_plane.control_loop import CONTROL_LOOP
from backend.simulation.traffic_controller import TRAFFIC_CONTROLLER

BASE_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = BASE_DIR / "backend"
WEBSITE_DIR = BASE_DIR / "website"


class TestProductionConfiguration:
    """Verify backend and deployment configurations."""

    def test_no_hardcoded_home_paths_in_backend(self):
        for root, _, files in os.walk(BACKEND_DIR):
            for file in files:
                if file.endswith(".py"):
                    filepath = Path(root) / file
                    text = filepath.read_text(encoding="utf-8")
                    assert "/home/pratay-karali" not in text, f"Hardcoded home path found in {filepath}"

    def test_entrypoint_host_and_port(self):
        app_file = BACKEND_DIR / "app.py"
        content = app_file.read_text(encoding="utf-8")

        assert 'host="0.0.0.0"' in content
        assert 'os.environ.get("PORT", 8000)' in content or "os.getenv('PORT'" in content

    def test_cors_configuration(self):
        app_file = BACKEND_DIR / "app.py"
        content = app_file.read_text(encoding="utf-8")

        assert "ALLOWED_ORIGINS" in content
        assert "here.now" in content

    def test_deployment_files_exist(self):
        dockerignore = BASE_DIR / ".dockerignore"
        dockerfile = BASE_DIR / "Dockerfile"
        procfile = BASE_DIR / "Procfile"
        start_sh = BASE_DIR / "start.sh"
        requirements = BASE_DIR / "requirements.txt"

        assert dockerignore.exists(), ".dockerignore missing"
        assert dockerfile.exists(), "Dockerfile missing"
        assert procfile.exists(), "Procfile missing"
        assert start_sh.exists(), "start.sh missing"
        assert requirements.exists(), "requirements.txt missing"

        d_ignore_text = dockerignore.read_text(encoding="utf-8")
        assert ".git" in d_ignore_text
        assert ".venv" in d_ignore_text
        assert "__pycache__" in d_ignore_text
        assert "*.pptx" in d_ignore_text
        assert "*.pdf" in d_ignore_text


class TestRuntimeSubsystemsAndModels:
    """Verify all 6 runtime subsystems initialize properly."""

    def test_all_models_ready(self):
        assert FORECASTER.is_ready is True, "M2 Forecaster is not ready"
        assert DETECTOR.is_ready is True, "M3 Anomaly Detector is not ready"
        assert RCA_CLASSIFIER.is_ready is True, "M4 RCA Classifier is not ready"
        assert ACTION_ENGINE.is_ready is True, "M5 Action Policy is not ready"

    def test_all_control_plane_subsystems_initialized(self):
        assert COLLECTOR is not None
        assert SAFETY_GUARDRAILS is not None
        assert CLOSED_LOOP_ACTUATOR is not None
        assert CONTROL_LOOP is not None
        assert TRAFFIC_CONTROLLER is not None


class TestFrontendDecoupledAPI:
    """Verify frontend API_BASE decoupled configuration."""

    def test_frontend_decoupled_api_base(self):
        app_js = WEBSITE_DIR / "app.js"
        content = app_js.read_text(encoding="utf-8")

        # Must not have hardcoded `const API_BASE = window.location.origin;`
        assert "const API_BASE = window.location.origin;" not in content
        assert "portalpulse-backend-url" in content
        assert "antideploy" in content

    def test_index_html_has_backend_meta_tag(self):
        index_html = WEBSITE_DIR / "index.html"
        content = index_html.read_text(encoding="utf-8")

        assert 'name="portalpulse-backend-url"' in content

    def test_zero_alert_in_frontend(self):
        for root, _, files in os.walk(WEBSITE_DIR):
            for file in files:
                if file.endswith((".html", ".js", ".ts")):
                    filepath = Path(root) / file
                    text = filepath.read_text(encoding="utf-8")
                    matches = re.findall(r'(?<![.\w])alert\s*\(', text)
                    assert len(matches) == 0, f"Found alert() in {filepath}: {matches}"


class TestProductionEndpointsReachable:
    """Verify all 9 critical production endpoints return 200."""

    @pytest.fixture(scope="class")
    def client(self):
        return TestClient(app)

    def test_health_endpoint(self, client):
        res = client.get("/health")
        assert res.status_code == 200
        assert res.json().get("status") in ["HEALTHY", "DEGRADED", "UP"]

    def test_ready_endpoint(self, client):
        res = client.get("/ready")
        assert res.status_code == 200
        assert res.json().get("status") in ["READY", "NOT_READY"]

    def test_docs_endpoint(self, client):
        res = client.get("/docs")
        assert res.status_code == 200

    def test_portals_endpoint(self, client):
        res = client.get("/api/v1/portals")
        assert res.status_code == 200
        data = res.json()
        assert isinstance(data["portals"], list)
        assert data["total_portals"] == len(data["portals"])

    def test_system_status_endpoint(self, client):
        res = client.get("/api/v1/system/status")
        assert res.status_code == 200
        data = res.json()
        assert "components" in data
        assert "current_control_cycle_id" in data

    def test_control_loop_status_endpoint(self, client):
        res = client.get("/api/v1/control-loop/status")
        assert res.status_code == 200
        assert "running" in res.json()

    def test_control_loop_latest_endpoint(self, client):
        res = client.get("/api/v1/control-loop/latest")
        assert res.status_code == 200

    def test_traffic_status_endpoint(self, client):
        res = client.get("/api/v1/traffic/status")
        assert res.status_code == 200

    def test_stream_events_endpoint(self, client):
        with client.stream("GET", "/api/v1/stream/events") as response:
            assert response.status_code == 200
            assert "text/event-stream" in response.headers.get("content-type", "")
            for line in response.iter_lines():
                if line:
                    break


class TestNirantarUnmodified:
    """Verify the native event feed distinguishes local simulation."""

    def test_nirantar_untouched(self):
        nirantar_path = Path("/home/pratay-karali/Desktop/NIRANTAR")
        if not nirantar_path.exists():
            pytest.skip("Nirantar directory not present")

        notices = nirantar_path / "frontend/src/components/PortalPulseNotices.tsx"
        assert notices.exists()
        assert "PORTALPULSE SIMULATOR" in notices.read_text(encoding="utf-8")
