"""Unit and integration test suite for PortalPulse Module 3 & 4 (Anomaly Detection & RCA).

Verifies:
1. IsolationForestAnomalyDetector feature extraction, anomaly scoring, and thresholding.
2. SystemTopologyDAG NetworkX graph integrity, anomaly scoring, and downstream-to-upstream causal propagation.
3. XGBoostRCAClassifier 8-category root cause classification, probabilities, and tactical mitigations.
4. FastAPI endpoints for live anomaly detection, live RCA, on-demand scenario diagnosis, and topology responses.
5. Training pipeline execution, dataset loaders, and model serialization.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch

import networkx as nx
import pytest
from fastapi.testclient import TestClient

from backend.app import app
from backend.m1_monitoring.collector import COLLECTOR
from backend.m1_monitoring.schema import RawTelemetry
from backend.m3_anomaly_rca.anomaly_detector import (
    ANOMALY_FEATURE_NAMES,
    IsolationForestAnomalyDetector,
)
from backend.m3_anomaly_rca.dependency_graph import (
    SYSTEM_NODES,
    SystemTopologyDAG,
)
from backend.m3_anomaly_rca.rca_classifier import (
    CATEGORY_NAMES,
    RECOMMENDED_PLAYBOOKS,
    XGBoostRCAClassifier,
)
from backend.m3_anomaly_rca.schema import (
    AnomalyResult,
    FailureCategory,
    RCAResult,
    TopologyGraphResponse,
)
from backend.m3_anomaly_rca.train_rca import (
    DATASET_PATH,
    generate_balanced_incident_dataset,
    load_nominal_telemetry_dataset,
    train_and_evaluate,
)

client = TestClient(app)


# ---------------------------------------------------------------------------
# Module 3: Isolation Forest Anomaly Detection Tests
# ---------------------------------------------------------------------------


class TestIsolationForestAnomalyDetector:
    """Test suite for unsupervised Isolation Forest anomaly scoring."""

    @pytest.fixture
    def nominal_telemetry(self) -> RawTelemetry:
        return RawTelemetry(
            active_users=8000,
            requests_per_sec=420.0,
            cpu_percent=38.0,
            ram_percent=42.0,
            network_in=35.0,
            network_out=80.0,
            response_time=65.0,
            throughput=418.0,
            error_rate=0.001,
            http_5xx=0.5,
            db_latency=25.0,
            db_connections=32.0,
            queue_length=2,
            service_instances=4,
        )

    @pytest.fixture
    def anomalous_telemetry(self) -> RawTelemetry:
        return RawTelemetry(
            active_users=75000,
            requests_per_sec=4200.0,
            cpu_percent=98.5,
            ram_percent=92.0,
            network_in=280.0,
            network_out=580.0,
            response_time=3200.0,
            throughput=2800.0,
            error_rate=0.28,
            http_5xx=950.0,
            db_latency=2400.0,
            db_connections=98.0,
            queue_length=1500,
            service_instances=4,
        )

    def test_nominal_evaluation(self, nominal_telemetry: RawTelemetry) -> None:
        """Nominal operational telemetry must evaluate as non-anomalous with low score."""
        detector = IsolationForestAnomalyDetector.load()
        result = detector.detect(nominal_telemetry)

        assert isinstance(result, AnomalyResult)
        assert not result.is_anomaly
        assert result.anomaly_score < 0.45
        assert result.severity == "NOMINAL"
        assert result.inference_time_ms >= 0.0

    def test_anomalous_evaluation(self, anomalous_telemetry: RawTelemetry) -> None:
        """Severe system degradation must trip anomaly trigger with CRITICAL severity."""
        detector = IsolationForestAnomalyDetector.load()
        result = detector.detect(anomalous_telemetry)

        assert isinstance(result, AnomalyResult)
        assert result.is_anomaly
        assert result.anomaly_score >= 0.50
        assert result.severity in ("WARNING", "CRITICAL")
        assert len(result.contributing_metrics) > 0

    def test_feature_extraction_types(self, nominal_telemetry: RawTelemetry) -> None:
        """Ensure feature extraction accepts RawTelemetry, dicts, and float lists."""
        detector = IsolationForestAnomalyDetector.load()

        # RawTelemetry
        vec_raw = detector.extract_features(nominal_telemetry)
        assert vec_raw.shape == (1, 8)

        # Dictionary
        data_dict = {
            "cpu_percent": 45.0,
            "ram_percent": 50.0,
            "requests_per_sec": 500.0,
            "response_time": 75.0,
            "error_rate": 0.002,
            "db_latency": 30.0,
            "db_connections": 35.0,
            "queue_length": 5.0,
        }
        vec_dict = detector.extract_features(data_dict)
        assert vec_dict.shape == (1, 8)

        # List
        vec_list = detector.extract_features([45.0, 50.0, 500.0, 75.0, 0.002, 30.0, 35.0, 5.0])
        assert vec_list.shape == (1, 8)

        # Error cases
        with pytest.raises(ValueError, match="Expected 8 features"):
            detector.extract_features([1.0, 2.0, 3.0])

        with pytest.raises(TypeError, match="Unsupported telemetry input type"):
            detector.extract_features("invalid_input")  # type: ignore

    def test_save_and_load_roundtrip(self, nominal_telemetry: RawTelemetry) -> None:
        """Detector state and baseline statistics must survive disk serialization."""
        detector = IsolationForestAnomalyDetector.load()
        with tempfile.TemporaryDirectory() as tmpdir:
            model_path = Path(tmpdir) / "test_iso_forest.pkl"
            detector.save(model_path)
            assert model_path.exists()

            loaded = IsolationForestAnomalyDetector.load(model_path)
            assert loaded.threshold == detector.threshold
            assert loaded.feature_names == detector.feature_names
            res_orig = detector.detect(nominal_telemetry)
            res_loaded = loaded.detect(nominal_telemetry)
            assert res_orig.is_anomaly == res_loaded.is_anomaly

    def test_detector_fit_and_missing_file_fallback(self) -> None:
        """Detector fit method updates statistics and missing model loads default."""
        detector = IsolationForestAnomalyDetector()
        import numpy as np

        X_synth = np.random.uniform(20.0, 80.0, size=(60, 8))
        detector.fit(X_synth, ANOMALY_FEATURE_NAMES)
        assert detector.is_fitted
        assert len(detector.feature_means) == 8

        non_existent = Path("/tmp/does_not_exist_portalpulse_iso.pkl")
        fallback_detector = IsolationForestAnomalyDetector.load(non_existent)
        assert isinstance(fallback_detector, IsolationForestAnomalyDetector)


# ---------------------------------------------------------------------------
# Module 4: NetworkX Topological Dependency DAG Tests
# ---------------------------------------------------------------------------


class TestSystemTopologyDAG:
    """Test suite for NetworkX architectural DAG and causal tracing."""

    @pytest.fixture
    def topology(self) -> SystemTopologyDAG:
        return SystemTopologyDAG()

    def test_dag_structure_and_acyclic(self, topology: SystemTopologyDAG) -> None:
        """Graph must contain all 6 tiers and satisfy strict DAG properties."""
        for node in SYSTEM_NODES:
            assert node in topology.traffic_dag
            assert node in topology.propagation_dag

        assert nx.is_directed_acyclic_graph(topology.traffic_dag)
        assert nx.is_directed_acyclic_graph(topology.propagation_dag)
        assert len(topology.traffic_dag.nodes) == 6
        assert len(topology.traffic_dag.edges) == 5

    def test_nominal_dag_state(self, topology: SystemTopologyDAG) -> None:
        """Healthy node metrics should produce NORMAL classification and low score."""
        nominal_metrics = {
            node: {"latency": 5.0, "error_rate": 0.0005, "cpu": 30.0}
            for node in SYSTEM_NODES
        }
        root, path, score = topology.trace_root_cause(nominal_metrics)
        assert root == "NORMAL"
        assert score < 0.35

    def test_downstream_database_root_cause(self, topology: SystemTopologyDAG) -> None:
        """Database saturation must be identified as root cause and propagated upstream to client."""
        db_outage_metrics = {
            "client": {"rps": 500.0, "users": 10000.0},
            "cdn_edge": {"latency": 45.0, "error_rate": 0.02},
            "api_gateway": {"latency": 850.0, "error_rate": 0.08, "queue": 15.0},
            "worker_backend": {"cpu": 40.0, "latency": 800.0, "error_rate": 0.08},
            "postgresql_db": {"db_latency": 2500.0, "db_connections": 96.0, "error_rate": 0.12},
            "redis_cache": {"latency": 2.0, "memory": 40.0, "error_rate": 0.0001},
        }
        root, path, score = topology.trace_root_cause(db_outage_metrics)

        assert root == "postgresql_db"
        assert score >= 0.70
        assert path == ["postgresql_db", "worker_backend", "api_gateway", "cdn_edge", "client"]

    def test_worker_backend_root_cause(self, topology: SystemTopologyDAG) -> None:
        """Worker pod compute exhaustion with healthy DB must isolate worker_backend."""
        worker_pegged_metrics = {
            "client": {"rps": 450.0, "users": 9000.0},
            "cdn_edge": {"latency": 30.0, "error_rate": 0.01},
            "api_gateway": {"latency": 900.0, "error_rate": 0.05, "queue": 20.0},
            "worker_backend": {"cpu_percent": 98.0, "ram_percent": 55.0, "error_rate": 0.05},
            "postgresql_db": {"db_latency": 22.0, "db_connections": 30.0, "error_rate": 0.001},
            "redis_cache": {"latency": 2.2, "memory": 35.0, "error_rate": 0.0001},
        }
        root, path, score = topology.trace_root_cause(worker_pegged_metrics)

        assert root == "worker_backend"
        assert score >= 0.70
        assert path == ["worker_backend", "api_gateway", "cdn_edge", "client"]

    def test_redis_cache_root_cause(self, topology: SystemTopologyDAG) -> None:
        """Redis degradation must propagate from redis_cache to client."""
        redis_metrics = {
            "client": {"rps": 400.0},
            "cdn_edge": {"latency": 25.0},
            "api_gateway": {"latency": 150.0},
            "worker_backend": {"cpu": 40.0},
            "postgresql_db": {"db_latency": 25.0, "db_connections": 25.0},
            "redis_cache": {"redis_latency": 55.0, "memory": 96.0, "error_rate": 0.06},
        }
        root, path, score = topology.trace_root_cause(redis_metrics)

        assert root == "redis_cache"
        assert path == ["redis_cache", "worker_backend", "api_gateway", "cdn_edge", "client"]

    def test_api_gateway_queue_root_cause(self, topology: SystemTopologyDAG) -> None:
        """Gateway queue jam must isolate api_gateway tier."""
        gw_metrics = {
            "client": {"rps": 800.0},
            "cdn_edge": {"latency": 35.0},
            "api_gateway": {"queue_length": 180.0, "response_time": 600.0, "error_rate": 0.12},
            "worker_backend": {"cpu": 45.0},
            "postgresql_db": {"db_latency": 25.0, "db_connections": 30.0},
            "redis_cache": {"latency": 2.0},
        }
        root, path, score = topology.trace_root_cause(gw_metrics)

        assert root == "api_gateway"
        assert path == ["api_gateway", "cdn_edge", "client"]

    def test_client_traffic_surge_root_cause(self, topology: SystemTopologyDAG) -> None:
        """Ingress flood origin must isolate client and trace forward."""
        client_surge_metrics = {
            "client": {"requests_per_sec": 4800.0, "active_users": 95000.0},
            "cdn_edge": {"network_latency": 20.0, "error_rate": 0.001},
            "api_gateway": {"queue_length": 5.0, "response_time": 60.0},
            "worker_backend": {"cpu_percent": 45.0},
            "postgresql_db": {"db_latency": 25.0, "db_connections": 35.0},
            "redis_cache": {"latency": 2.0},
        }
        root, path, score = topology.trace_root_cause(client_surge_metrics)
        assert root == "client"
        assert score >= 0.70
        assert "client" in path

    def test_synthesize_node_metrics(self, topology: SystemTopologyDAG) -> None:
        """Synthesized metrics must populate all 6 architectural nodes."""
        raw = RawTelemetry(
            active_users=15000,
            requests_per_sec=900.0,
            cpu_percent=55.0,
            ram_percent=60.0,
            network_in=45.0,
            network_out=110.0,
            response_time=120.0,
            throughput=895.0,
            error_rate=0.005,
            http_5xx=4.5,
            db_latency=45.0,
            db_connections=50.0,
            queue_length=12,
            service_instances=4,
        )
        synth = topology.synthesize_node_metrics(raw)
        assert len(synth) == 6
        for node in SYSTEM_NODES:
            assert node in synth
            assert len(synth[node]) > 0

    def test_topology_response_generation(self, topology: SystemTopologyDAG) -> None:
        """Topology response structure must include nodes, edges, and system health status."""
        resp = topology.get_topology_response()
        assert isinstance(resp, TopologyGraphResponse)
        assert len(resp.nodes) == 6
        assert len(resp.edges) == 5
        assert resp.system_health in ("HEALTHY", "DEGRADED", "CRITICAL")

        # Critical health check branch
        critical_metrics = {
            "postgresql_db": {"db_latency": 3500.0, "db_connections": 99.0, "error_rate": 0.25}
        }
        resp_crit = topology.get_topology_response(critical_metrics)
        assert resp_crit.system_health in ("DEGRADED", "CRITICAL")
        assert resp_crit.root_cause_node == "postgresql_db"


# ---------------------------------------------------------------------------
# Module 4: Supervised XGBoost RCA Classifier Tests
# ---------------------------------------------------------------------------


class TestXGBoostRCAClassifier:
    """Test suite for 8-class XGBoost root cause analysis attribution."""

    @pytest.fixture
    def rca(self) -> XGBoostRCAClassifier:
        return XGBoostRCAClassifier.load()

    @pytest.mark.parametrize(
        "expected_category,features",
        [
            (
                FailureCategory.NORMAL,
                [38.0, 42.0, 450.0, 65.0, 0.001, 24.0, 32.0, 2.0],
            ),
            (
                FailureCategory.TRAFFIC_SPIKE,
                [78.0, 68.0, 4200.0, 450.0, 0.03, 75.0, 78.0, 320.0],
            ),
            (
                FailureCategory.API_CPU,
                [98.5, 55.0, 420.0, 1400.0, 0.04, 25.0, 35.0, 30.0],
            ),
            (
                FailureCategory.DATABASE,
                [38.0, 48.0, 320.0, 2200.0, 0.08, 1850.0, 97.0, 40.0],
            ),
            (
                FailureCategory.NETWORK,
                [26.0, 35.0, 160.0, 2400.0, 0.22, 22.0, 24.0, 5.0],
            ),
            (
                FailureCategory.MEMORY,
                [76.0, 97.5, 360.0, 920.0, 0.07, 32.0, 42.0, 25.0],
            ),
            (
                FailureCategory.QUEUE_OVERLOAD,
                [82.0, 68.0, 1300.0, 1850.0, 0.06, 42.0, 58.0, 2200.0],
            ),
            (
                FailureCategory.DEPENDENCY_FAILURE,
                [30.0, 44.0, 280.0, 3100.0, 0.52, 24.0, 28.0, 15.0],
            ),
        ],
    )
    def test_rca_classification_scenarios(
        self,
        rca: XGBoostRCAClassifier,
        expected_category: FailureCategory,
        features: list[float],
    ) -> None:
        """Each fault pattern must be correctly classified with confidence >= 0.70."""
        result = rca.classify(features)

        assert isinstance(result, RCAResult)
        assert result.primary_root_cause == expected_category
        assert result.confidence >= 0.70
        assert len(result.probabilities) == 8
        prob_sum = sum(result.probabilities.values())
        assert abs(prob_sum - 1.0) < 0.02
        assert len(result.causal_propagation_chain) >= 1
        assert result.recommended_mitigation == RECOMMENDED_PLAYBOOKS[expected_category]
        assert result.inference_time_ms < 10.0

    def test_save_and_load_roundtrip(self, rca: XGBoostRCAClassifier) -> None:
        """RCA classifier must serialize and reload with matching inference outputs."""
        sample = [98.0, 55.0, 420.0, 1400.0, 0.04, 25.0, 35.0, 30.0]
        with tempfile.TemporaryDirectory() as tmpdir:
            model_path = Path(tmpdir) / "test_xgboost_rca.pkl"
            rca.save(model_path)
            assert model_path.exists()

            loaded = XGBoostRCAClassifier.load(model_path)
            orig_res = rca.classify(sample)
            loaded_res = loaded.classify(sample)
            assert orig_res.primary_root_cause == loaded_res.primary_root_cause
            assert abs(orig_res.confidence - loaded_res.confidence) < 1e-4

        non_existent = Path("/tmp/does_not_exist_portalpulse_rca.pkl")
        fallback_rca = XGBoostRCAClassifier.load(non_existent)
        assert isinstance(fallback_rca, XGBoostRCAClassifier)

    def test_rca_feature_validation_errors(self, rca: XGBoostRCAClassifier) -> None:
        """Extract features error checks on invalid input shapes or types."""
        with pytest.raises(ValueError, match="Expected 8 features"):
            rca.extract_features([1.0, 2.0])

        with pytest.raises(TypeError, match="Unsupported telemetry input type"):
            rca.extract_features(12345)  # type: ignore


# ---------------------------------------------------------------------------
# Integration Tests: FastAPI Endpoints
# ---------------------------------------------------------------------------


class TestM3M4FastAPIEndpoints:
    """Integration test suite for FastAPI anomaly & RCA routes."""

    def test_root_endpoint_active_modules(self) -> None:
        """GET / should report M3 and M4 as active modules."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "M3_ANOMALY_ISOLATION_FOREST" in data["active_modules"]
        assert "M4_RCA_XGBOOST_NETWORKX" in data["active_modules"]

    def test_get_live_anomaly(self) -> None:
        """GET /api/v1/anomaly/live should return valid AnomalyResult."""
        response = client.get("/api/v1/anomaly/live")
        assert response.status_code == 200
        data = response.json()
        assert "is_anomaly" in data
        assert "anomaly_score" in data
        assert 0.0 <= data["anomaly_score"] <= 1.0
        assert data["severity"] in ("NOMINAL", "WARNING", "CRITICAL")
        assert "contributing_metrics" in data
        assert "inference_time_ms" in data

    def test_get_live_rca(self) -> None:
        """GET /api/v1/rca/live should return valid RCAResult."""
        response = client.get("/api/v1/rca/live")
        assert response.status_code == 200
        data = response.json()
        assert "primary_root_cause" in data
        assert data["primary_root_cause"] in CATEGORY_NAMES
        assert 0.0 <= data["confidence"] <= 1.0
        assert "probabilities" in data
        assert "root_cause_tier" in data
        assert "causal_propagation_chain" in data
        assert "recommended_mitigation" in data

    def test_post_rca_diagnose_database_jam(self) -> None:
        """POST /api/v1/rca/diagnose should classify database lock jam scenario."""
        payload = {
            "cpu_percent": 40.0,
            "ram_percent": 50.0,
            "requests_per_sec": 300.0,
            "response_time": 2400.0,
            "error_rate": 0.12,
            "db_latency": 2100.0,
            "db_connections": 98.0,
            "queue_length": 50.0,
        }
        response = client.post("/api/v1/rca/diagnose", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["primary_root_cause"] == FailureCategory.DATABASE.value
        assert data["confidence"] >= 0.70
        assert data["root_cause_tier"] == "postgresql_db"
        assert "postgresql_db" in data["causal_propagation_chain"]

    def test_post_rca_diagnose_cpu_saturation(self) -> None:
        """POST /api/v1/rca/diagnose should classify API CPU saturation scenario."""
        payload = {
            "cpu_percent": 98.0,
            "ram_percent": 55.0,
            "requests_per_sec": 450.0,
            "response_time": 1500.0,
            "error_rate": 0.04,
            "db_latency": 24.0,
            "db_connections": 32.0,
            "queue_length": 25.0,
        }
        response = client.post("/api/v1/rca/diagnose", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["primary_root_cause"] == FailureCategory.API_CPU.value
        assert data["confidence"] >= 0.70
        assert data["root_cause_tier"] == "worker_backend"

    def test_get_topology_graph(self) -> None:
        """GET /api/v1/rca/topology should return full 6-node architectural graph."""
        response = client.get("/api/v1/rca/topology")
        assert response.status_code == 200
        data = response.json()
        assert "nodes" in data
        assert len(data["nodes"]) == 6
        assert "edges" in data
        assert len(data["edges"]) == 5
        assert "system_health" in data
        assert data["system_health"] in ("HEALTHY", "DEGRADED", "CRITICAL")

    def test_get_rca_metadata(self) -> None:
        """GET /api/v1/rca/metadata should return saved model evaluation stats."""
        response = client.get("/api/v1/rca/metadata")
        assert response.status_code == 200
        data = response.json()
        assert "model_name" in data
        assert "evaluation" in data
        assert data["evaluation"]["macro_f1"] >= 0.92
        assert data["evaluation"]["inference_latency_ms"]["p95"] < 2.0

    def test_live_routes_with_empty_collector(self) -> None:
        """Endpoints should automatically generate synthetic step when collector has no telemetry."""
        with patch.object(COLLECTOR, "get_latest_status", return_value=None):
            resp_anomaly = client.get("/api/v1/anomaly/live")
            assert resp_anomaly.status_code == 200

            resp_rca = client.get("/api/v1/rca/live")
            assert resp_rca.status_code == 200

            resp_topo = client.get("/api/v1/rca/topology")
            assert resp_topo.status_code == 200

    def test_metadata_not_found(self) -> None:
        """GET /api/v1/rca/metadata raises 404 if file does not exist."""
        with patch("backend.m3_anomaly_rca.routes.METADATA_PATH", Path("/tmp/nonexistent_meta.json")):
            resp = client.get("/api/v1/rca/metadata")
            assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Training Pipeline & Data Loader Tests
# ---------------------------------------------------------------------------


class TestTrainingPipeline:
    """Test suite for synthetic incident generation, nominal dataset loading, and training pipeline."""

    def test_generate_balanced_incident_dataset(self) -> None:
        """Synthetic generator must generate balanced classes and correct 8-feature dimensions."""
        X, y = generate_balanced_incident_dataset(n_samples_per_class=20, random_state=42)
        assert X.shape == (160, 8)
        assert y.shape == (160,)
        for class_idx in range(8):
            assert (y == class_idx).sum() == 20

    def test_load_nominal_dataset(self) -> None:
        """Nominal dataset loader extracts and couples features from clean CSV."""
        X_nom = load_nominal_telemetry_dataset(DATASET_PATH)
        assert X_nom.shape[1] == 8
        assert len(X_nom) > 1000

        with pytest.raises(FileNotFoundError):
            load_nominal_telemetry_dataset(Path("/tmp/nonexistent_data.csv"))

    def test_train_and_evaluate_pipeline_execution(self) -> None:
        """Execute end-to-end training and verify artifact serialization and metrics."""
        with tempfile.TemporaryDirectory() as tmpdir:
            out_dir = Path(tmpdir) / "models"
            meta = train_and_evaluate(n_samples_per_class=35, output_dir=out_dir)

            assert (out_dir / "isolation_forest.pkl").exists()
            assert (out_dir / "xgboost_rca.pkl").exists()
            assert (out_dir / "rca_metadata.json").exists()
            assert "macro_f1" in meta["evaluation"]
            assert meta["evaluation"]["macro_f1"] > 0.80
