"""
tests/test_module10_rca_dag.py
Comprehensive test suite for Module 10: Interactive NetworkX RCA Causal DAG
Validates:
1. ResultDayCausalDAG construction in NetworkX DiGraph
2. All 8 nodes and branching topology:
   RESULT DAY -> TRAFFIC SPIKE -> API LOAD -> (DB POOL 🔴 / CPU) -> QUERY WAIT -> LATENCY -> 503
3. Active causal path highlighting and bottleneck isolation
4. FastAPI endpoint GET /api/v1/rca/causal-dag
5. Frontend elements in website/index.html (inline tree, clickable triggers, modal dialog)
6. CSS styles in website/style.css
7. Zero alert() calls in frontend files
"""

import os
import re
import pytest
import networkx as nx
from fastapi.testclient import TestClient

from backend.app import app
from backend.m3_anomaly_rca.dependency_graph import (
    ResultDayCausalDAG,
    RESULT_DAY_CAUSAL_DAG,
)


def test_networkx_dag_structure_and_nodes():
    """Verify NetworkX DiGraph contains all 8 nodes with proper attributes."""
    dag = ResultDayCausalDAG()
    G = dag.graph

    assert isinstance(G, nx.DiGraph)
    assert G.number_of_nodes() == 8
    assert G.number_of_edges() == 7

    expected_nodes = [
        "RESULT_DAY",
        "TRAFFIC_SPIKE",
        "API_LOAD",
        "DB_POOL",
        "CPU",
        "QUERY_WAIT",
        "LATENCY",
        "ERR_503",
    ]
    for node in expected_nodes:
        assert G.has_node(node), f"Node '{node}' missing from NetworkX DAG"

    # Verify DB_POOL is flagged as bottleneck and CPU is not
    assert G.nodes["DB_POOL"].get("is_bottleneck") is True
    assert G.nodes["CPU"].get("is_bottleneck") is False


def test_networkx_branching_topology():
    """Verify exact branching topology: API LOAD branches to DB POOL and CPU."""
    dag = ResultDayCausalDAG()
    G = dag.graph

    # Ingress to API LOAD
    assert G.has_edge("RESULT_DAY", "TRAFFIC_SPIKE")
    assert G.has_edge("TRAFFIC_SPIKE", "API_LOAD")

    # Branch from API LOAD
    assert G.has_edge("API_LOAD", "DB_POOL")
    assert G.has_edge("API_LOAD", "CPU")

    # Cascading contention from DB POOL
    assert G.has_edge("DB_POOL", "QUERY_WAIT")
    assert G.has_edge("QUERY_WAIT", "LATENCY")
    assert G.has_edge("LATENCY", "ERR_503")

    # CPU does not connect directly to 503 in Result-Day DB saturation
    assert not G.has_edge("CPU", "QUERY_WAIT")
    assert not G.has_edge("CPU", "ERR_503")


def test_active_causal_path_highlighting():
    """Verify active causal path correctly highlights the bottleneck chain."""
    dag = ResultDayCausalDAG()
    active_path = dag.get_active_causal_path()

    expected_active_path = [
        "RESULT_DAY",
        "TRAFFIC_SPIKE",
        "API_LOAD",
        "DB_POOL",
        "QUERY_WAIT",
        "LATENCY",
        "ERR_503",
    ]
    assert active_path == expected_active_path

    # Serialized dictionary must mark is_active on nodes and edges
    data = dag.to_dict({
        "virtual_users": 12481,
        "requests_per_sec": 4820,
        "db_connections": 48,
        "cpu_percent": 78.0,
        "latency_ms": 2410.0,
        "error_rate": 5.8,
    })

    assert data["engine"] == "NetworkX DiGraph"
    assert data["root_cause"] == "DATABASE"
    assert data["root_cause_node"] == "DB_POOL"
    assert data["confidence"] == 0.912
    assert "ascii_diagram" in data

    nodes_map = {n["id"]: n for n in data["nodes"]}
    assert nodes_map["DB_POOL"]["is_active"] is True
    assert nodes_map["DB_POOL"]["is_bottleneck"] is True
    assert nodes_map["DB_POOL"]["status"] == "CRITICAL"

    assert nodes_map["CPU"]["is_active"] is False
    assert nodes_map["CPU"]["is_bottleneck"] is False
    assert nodes_map["CPU"]["status"] == "NOMINAL"


def test_api_causal_dag_endpoint():
    """Verify GET /api/v1/rca/causal-dag returns 200 with complete DAG data."""
    client = TestClient(app)
    resp = client.get("/api/v1/rca/causal-dag")
    assert resp.status_code == 200
    json_data = resp.json()

    assert json_data["engine"] == "NetworkX DiGraph"
    assert len(json_data["nodes"]) == 8
    assert len(json_data["edges"]) == 7
    assert "active_causal_path" in json_data
    assert "DB_POOL" in json_data["active_causal_path"]


def test_frontend_causal_dag_html_elements():
    """Verify index.html contains clickable RCA triggers, inline DAG, and modal."""
    html_path = os.path.join(os.path.dirname(__file__), "..", "website", "index.html")
    with open(html_path, "r", encoding="utf-8") as f:
        html = f.read()

    # Clickable card and control-path node
    assert 'id="cardM4Rca"' in html
    assert 'clickable-rca' in html
    assert 'PortalApp.openRcaDagModal()' in html
    assert 'id="lrNodeM4"' in html

    # Inline 2D DAG structure in Card M4
    assert 'id="lrDagInlineTree"' in html
    assert 'RESULT DAY' in html
    assert 'TRAFFIC SPIKE' in html
    assert 'API LOAD' in html
    assert 'DB POOL 🔴' in html
    assert 'CPU' in html
    assert 'QUERY WAIT' in html
    assert 'LATENCY' in html
    assert '503' in html

    # Modal Dialog & Elements
    assert 'id="lrRcaDagModal"' in html
    assert 'id="lrDagModalDialog"' in html
    assert 'id="lrDagActivePathPills"' in html
    assert 'id="lrModalDagTree"' in html
    assert 'id="mDagNode_DB_POOL"' in html
    assert 'id="mDagNode_CPU"' in html
    assert 'id="lrDagSelectedName"' in html
    assert 'id="lrDagSelectedBadge"' in html
    assert 'id="lrDagSelectedMetric"' in html
    assert 'NetworkX DiGraph Engine' in html


def test_css_causal_dag_styles():
    """Verify style.css defines the DAG layout and animation styles."""
    css_path = os.path.join(os.path.dirname(__file__), "..", "website", "style.css")
    with open(css_path, "r", encoding="utf-8") as f:
        css = f.read()

    assert ".clickable-rca" in css
    assert ".lr-dag-dialog" in css
    assert ".lr-dag-path-banner" in css
    assert ".dag-node-bottleneck" in css
    assert ".dag-node-active" in css
    assert ".dag-node-nominal" in css
    assert ".dag-branch-split" in css
    assert "pulse-red-glow" in css


def test_zero_alert_in_frontend():
    """Verify strict prohibition of alert() across all frontend code."""
    website_dir = os.path.join(os.path.dirname(__file__), "..", "website")
    for fname in ["index.html", "app.js"]:
        fpath = os.path.join(website_dir, fname)
        with open(fpath, "r", encoding="utf-8") as f:
            content = f.read()
        alerts = re.findall(r'(?<![a-zA-Z0-9_])alert\(', content)
        assert len(alerts) == 0, f"Found alert() in {fname}: {alerts}"
