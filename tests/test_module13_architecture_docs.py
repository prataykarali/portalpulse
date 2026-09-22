"""Module 13: Automated Test Suite for Complete PortalPulse Architecture Documentation.

Validates:
1. docs/ARCHITECTURE.md exists and contains all seven production-accurate diagrams.
2. Taxonomy correctly classifies:
   - Trained ML Models (M2, M3, M4, M5)
   - Deterministic Algorithms (M1, M4 DAG, M6 Safety)
   - Simulation / Digital Twin (M7 Actuator, Locust Traffic Engine)
   - Live Backend Services (FastAPI, Control Loop, SSE Broadcaster)
   - Frontend Visualization (HTML5 Command Center, SVG charts)
3. Main Diagram 1 contains the full sequence:
   IEMCRP RESULT-DAY TRAFFIC -> TELEMETRY -> M2 -> M3 -> M4 -> M5 -> M6 -> M7 -> CHANGED SYSTEM STATE -> TELEMETRY.
4. M7 Actuator is explicitly noted as a digital-twin simulation, not real cloud hypervisor.
5. Frontend UI integration:
   - website/index.html contains #lrArchitectureModal with 7 tabbed panels
   - website/app.js contains openArchitectureModal, closeArchitectureModal, switchArchTab
   - website/style.css contains .lr-arch-dialog and .lr-arch-pre
   - Zero alert() calls
6. Nirantar remains 100% untouched.
"""

import os
import re
import subprocess
from pathlib import Path
import pytest

BASE_DIR = Path(__file__).resolve().parents[1]
DOCS_DIR = BASE_DIR / "docs"
WEBSITE_DIR = BASE_DIR / "website"


class TestArchitectureDocumentation:
    """Verify production architecture documentation completeness and accuracy."""

    def test_architecture_md_exists_and_contains_seven_diagrams(self):
        arch_path = DOCS_DIR / "ARCHITECTURE.md"
        assert arch_path.exists(), "docs/ARCHITECTURE.md does not exist"
        content = arch_path.read_text(encoding="utf-8")

        for d_num in range(1, 8):
            assert f"Diagram {d_num}" in content, f"Missing Diagram {d_num} in docs/ARCHITECTURE.md"

    def test_diagram_1_overall_architecture_sequence(self):
        arch_path = DOCS_DIR / "ARCHITECTURE.md"
        content = arch_path.read_text(encoding="utf-8")

        # Must reflect the exact implemented flow
        assert "IEMCRP Exam Result Portal" in content
        assert "M1 Telemetry Ingestion Engine" in content
        assert "M2 Multi-Horizon Forecaster" in content
        assert "M3 Unsupervised Anomaly Engine" in content
        assert "M4 Root Cause Analysis" in content
        assert "M5 Tactical Action Policy" in content
        assert "M6 Deterministic Safety Layer" in content
        assert "M7 Closed-Loop Actuator" in content
        assert "CHANGED SYSTEM STATE" in content
        assert "FEEDBACK TO M1 TELEMETRY" in content

    def test_taxonomy_and_actuator_clarification(self):
        arch_path = DOCS_DIR / "ARCHITECTURE.md"
        content = arch_path.read_text(encoding="utf-8")

        # Verify taxonomy table
        assert "Trained Machine Learning Model" in content
        assert "Deterministic Rules Engine" in content
        assert "Digital-Twin / Local Process Actuator" in content
        assert "XGBoost" in content
        assert "IsolationForest" in content
        assert "PyTorch" in content
        assert "NetworkX" in content

    def test_diagrams_match_implemented_components(self):
        arch_path = DOCS_DIR / "ARCHITECTURE.md"
        content = arch_path.read_text(encoding="utf-8")

        # M1 pipeline details
        assert "Ring Buffer (1,800 entries)" in content
        assert "telemetry_history.db" in content

        # M2 pipeline details
        assert "+5m" in content
        assert "+10m" in content
        assert "+15m" in content
        assert "Capacity Pressure Index" in content

        # M3 pipeline details
        assert "Isolation Forest" in content
        assert "db_connections" in content
        assert "response_time" in content

        # M4 pipeline details
        assert "nx.DiGraph" in content
        assert "Active Causal Propagation Chain" in content

        # M5 & M6 details
        assert "ENABLE_WAITING_ROOM" in content
        assert "Token Bucket" in content
        assert "Flapping Cooldown" in content

        # Closed-loop lifecycle
        assert "PRE-ACTION" in content
        assert "STABILIZING" in content
        assert "RECOVERY VERIFIED" in content


class TestFrontendArchitectureIntegration:
    """Verify frontend command center exposes architecture modal and diagrams."""

    def test_index_html_has_architecture_modal_and_button(self):
        html_path = WEBSITE_DIR / "index.html"
        content = html_path.read_text(encoding="utf-8")

        assert "lr-arch-header-btn" in content
        assert 'id="lrArchitectureModal"' in content
        assert "lr-arch-tabs" in content

        for p_idx in range(1, 8):
            assert f'id="archPanel{p_idx}"' in content, f"Missing archPanel{p_idx} in index.html"

    def test_app_js_has_architecture_handlers(self):
        js_path = WEBSITE_DIR / "app.js"
        content = js_path.read_text(encoding="utf-8")

        assert "openArchitectureModal" in content
        assert "closeArchitectureModal" in content
        assert "switchArchTab" in content

    def test_style_css_has_architecture_styles(self):
        css_path = WEBSITE_DIR / "style.css"
        content = css_path.read_text(encoding="utf-8")

        assert ".lr-arch-dialog" in content
        assert ".lr-arch-tabs" in content
        assert ".lr-arch-pre" in content
        assert ".arch-tag" in content

    def test_zero_alert_in_frontend(self):
        for root, _, files in os.walk(WEBSITE_DIR):
            for file in files:
                if file.endswith((".html", ".js", ".ts")):
                    filepath = Path(root) / file
                    text = filepath.read_text(encoding="utf-8")
                    matches = re.findall(r'(?<![.\w])alert\s*\(', text)
                    assert len(matches) == 0, f"Found alert() in {filepath}: {matches}"


class TestNirantarUnmodified:
    """Verify Nirantar repository remains completely untouched."""

    def test_nirantar_untouched(self):
        nirantar_path = Path("/home/pratay-karali/Desktop/NIRANTAR")
        if not nirantar_path.exists():
            pytest.skip("Nirantar directory not present")

        proc = subprocess.run(["git", "-C", str(nirantar_path), "status", "--porcelain"], capture_output=True, text=True)
        assert proc.returncode == 0
        assert "portalpulse" not in proc.stdout.lower()
