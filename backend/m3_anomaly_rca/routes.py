"""PortalPulse Module 3 & 4: Anomaly Detection & Root Cause Analysis API Routes.

FastAPI endpoints for live anomaly detection, live RCA classification,
on-demand diagnostic simulation, and topological dependency graph traversal.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, cast

from fastapi import APIRouter, HTTPException

from backend.m1_monitoring.collector import COLLECTOR
from backend.m1_monitoring.portal_simulator import PortalSimulator
from backend.m3_anomaly_rca.anomaly_detector import DETECTOR
from backend.m3_anomaly_rca.dependency_graph import RESULT_DAY_CAUSAL_DAG, TOPOLOGY_DAG
from backend.m3_anomaly_rca.rca_classifier import RCA_CLASSIFIER
from backend.m3_anomaly_rca.schema import (
    AnomalyResult,
    RCADiagnoseRequest,
    RCAResult,
    TopologyGraphResponse,
)

router = APIRouter(tags=["M3 & M4: Anomaly Detection & Root Cause Analysis"])
SIMULATOR = PortalSimulator()

METADATA_PATH = Path(__file__).resolve().parent / "models" / "rca_metadata.json"


@router.get("/api/v1/anomaly/live", response_model=AnomalyResult)
def get_live_anomaly() -> AnomalyResult:
    """Run unsupervised Isolation Forest anomaly scoring on live system telemetry."""
    status = COLLECTOR.get_latest_status()
    if not status:
        initial_raw = SIMULATOR.generate_step()
        status = COLLECTOR.record_telemetry(initial_raw, SIMULATOR.config.scenario_type)

    return DETECTOR.detect(status.raw)


@router.get("/api/v1/rca/live", response_model=RCAResult)
def get_live_rca() -> RCAResult:
    """Run XGBoost RCA classification and NetworkX causal graph tracing on live telemetry."""
    status = COLLECTOR.get_latest_status()
    if not status:
        initial_raw = SIMULATOR.generate_step()
        status = COLLECTOR.record_telemetry(initial_raw, SIMULATOR.config.scenario_type)

    return RCA_CLASSIFIER.classify(status.raw)


@router.post("/api/v1/rca/diagnose", response_model=RCAResult)
def diagnose_rca(payload: RCADiagnoseRequest) -> RCAResult:
    """Diagnose an on-demand incident scenario using custom metric inputs."""
    data = payload.model_dump()
    node_metrics = payload.node_metrics
    return RCA_CLASSIFIER.classify(data, node_metrics=node_metrics)


@router.get("/api/v1/rca/topology", response_model=TopologyGraphResponse)
def get_topology_graph() -> TopologyGraphResponse:
    """Retrieve 6-tier architectural DAG with live node health and causal propagation."""
    status = COLLECTOR.get_latest_status()
    if not status:
        initial_raw = SIMULATOR.generate_step()
        status = COLLECTOR.record_telemetry(initial_raw, SIMULATOR.config.scenario_type)

    node_metrics = TOPOLOGY_DAG.synthesize_node_metrics(status.raw)
    return TOPOLOGY_DAG.get_topology_response(node_metrics)


@router.get("/api/v1/rca/causal-dag")
def get_causal_dag() -> Dict[str, Any]:
    """Retrieve NetworkX-powered Result-Day Causal DAG with highlighted active path."""
    status = COLLECTOR.get_latest_status()
    raw = {}
    if status and hasattr(status, "raw"):
        raw = (
            status.raw.model_dump()
            if hasattr(status.raw, "model_dump")
            else (status.raw.dict() if hasattr(status.raw, "dict") else {})
        )
    return RESULT_DAY_CAUSAL_DAG.to_dict(raw)


@router.get("/api/v1/rca/metadata", response_model=Dict[str, Any])
def get_rca_metadata() -> Dict[str, Any]:
    """Retrieve RCA model evaluation metrics, confusion matrix, and hyperparameters."""
    if not METADATA_PATH.exists():
        raise HTTPException(
            status_code=404,
            detail="RCA metadata not found. Please run train_rca.py first.",
        )
    return cast(Dict[str, Any], json.loads(METADATA_PATH.read_text()))
