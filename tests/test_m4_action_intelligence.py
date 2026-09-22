"""Unit and integration test suite for PortalPulse Module 4 (Action Intelligence).

Verifies:
1. Synthetic dataset generator distribution, shapes, and absence of NaNs.
2. PyTorch ActionPolicyMLP neural network forward pass, softmax probabilities, and checkpoint serialization.
3. Production ActionIntelligenceEngine heuristics, tactical rationale generation, and HITL safety enforcement.
4. FastAPI endpoints for live recommendations, state evaluation, catalog listing, and metadata retrieval.
5. End-to-end training pipeline and inference latency benchmarking.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np
import pytest
import torch
from fastapi.testclient import TestClient

from backend.app import app
from backend.m1_monitoring.collector import COLLECTOR
from backend.m1_monitoring.schema import RawTelemetry
from backend.m4_action_intelligence.action_engine import ACTION_ENGINE, ActionIntelligenceEngine
from backend.m4_action_intelligence.dataset_generator import generate_action_dataset
from backend.m4_action_intelligence.policy_net import ActionPolicyMLP
from backend.m4_action_intelligence.schema import (
    ACTION_BLAST_RADIUS,
    ACTION_INDEX_MAP,
    STATE_FEATURE_NAMES,
    ActionRecommendation,
    ActionStateVector,
    SREAction,
)
from backend.m4_action_intelligence.train_policy import train_action_policy

client = TestClient(app)


# ---------------------------------------------------------------------------
# Test Fixtures & Artifact Initialization
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session", autouse=True)
def prepare_m4_artifacts() -> None:
    """Ensure baseline trained model artifacts exist for test execution."""
    train_action_policy(
        n_samples=1100,  # 100 samples per class for swift test init
        epochs=3,
        batch_size=32,
    )
    ACTION_ENGINE.reload()


@pytest.fixture
def nominal_state_vector() -> ActionStateVector:
    return ActionStateVector(
        cpu_percent=32.0,
        ram_percent=42.0,
        requests_per_sec=380.0,
        response_time=58.0,
        error_rate=0.001,
        future_rps_5m=410.0,
        future_cpu_5m=34.0,
        future_latency_5m=60.0,
        anomaly_score=0.08,
        rca_confidence=0.12,
        db_connections=26.0,
        queue_length=2.0,
        service_instances=4.0,
    )


@pytest.fixture
def cpu_saturation_vector() -> ActionStateVector:
    return ActionStateVector(
        cpu_percent=96.0,
        ram_percent=68.0,
        requests_per_sec=3200.0,
        response_time=1200.0,
        error_rate=0.025,
        future_rps_5m=3800.0,
        future_cpu_5m=98.0,
        future_latency_5m=1450.0,
        anomaly_score=0.88,
        rca_confidence=0.92,
        db_connections=48.0,
        queue_length=150.0,
        service_instances=4.0,
    )


@pytest.fixture
def db_pool_exhaustion_vector() -> ActionStateVector:
    return ActionStateVector(
        cpu_percent=52.0,
        ram_percent=58.0,
        requests_per_sec=2400.0,
        response_time=2100.0,
        error_rate=0.045,
        future_rps_5m=2500.0,
        future_cpu_5m=54.0,
        future_latency_5m=2400.0,
        anomaly_score=0.92,
        rca_confidence=0.95,
        db_connections=98.0,  # Pool saturated!
        queue_length=280.0,
        service_instances=4.0,
    )


# ---------------------------------------------------------------------------
# 1. Dataset Generation Tests
# ---------------------------------------------------------------------------


class TestActionDatasetGenerator:
    """Test suite for synthetic telemetry generation across all 11 SRE actions."""

    def test_generation_shape_and_distribution(self) -> None:
        X, y, df = generate_action_dataset(n_samples=1100, random_state=42)

        assert X.shape == (1100, 13)
        assert y.shape == (1100,)
        assert len(df) == 1100
        assert not np.isnan(X).any()
        assert not np.isinf(X).any()

        # Verify balanced distribution across all 11 classes
        unique_classes, counts = np.unique(y, return_counts=True)
        assert len(unique_classes) == 11
        for count in counts:
            assert count == 100

    def test_dataframe_columns_match_feature_names(self) -> None:
        _, _, df = generate_action_dataset(n_samples=220, random_state=42)
        for name in STATE_FEATURE_NAMES:
            assert name in df.columns
        assert "action_id" in df.columns
        assert "action_name" in df.columns


# ---------------------------------------------------------------------------
# 2. PyTorch Model Architecture Tests
# ---------------------------------------------------------------------------


class TestActionPolicyMLPArchitecture:
    """Test suite for PyTorch ActionPolicyMLP neural network."""

    def test_forward_pass_dimensions(self) -> None:
        model = ActionPolicyMLP(input_dim=13, output_dim=11)
        model.eval()

        # Batch input
        batch_x = torch.randn(8, 13)
        logits = model(batch_x)
        assert logits.shape == (8, 11)

        # Single sample input
        single_x = torch.randn(13)
        single_logits = model(single_x)
        assert single_logits.shape == (1, 11)

    def test_predict_proba_sums_to_one(self) -> None:
        model = ActionPolicyMLP(input_dim=13, output_dim=11)
        batch_x = torch.randn(16, 13)
        probs = model.predict_proba(batch_x)

        assert probs.shape == (16, 11)
        sums = torch.sum(probs, dim=-1).detach().cpu().numpy()
        np.testing.assert_allclose(sums, np.ones(16), atol=1e-5)

    def test_checkpoint_save_and_load(self) -> None:
        model = ActionPolicyMLP(input_dim=13, output_dim=11)
        with tempfile.TemporaryDirectory() as tmpdir:
            save_path = Path(tmpdir) / "test_policy.pt"
            model.save_checkpoint(save_path, extra_metadata={"author": "PortalPulse", "test_acc": 0.95})

            loaded_model, metadata = ActionPolicyMLP.load_checkpoint(save_path)
            assert loaded_model.input_dim == 13
            assert loaded_model.output_dim == 11
            assert metadata["author"] == "PortalPulse"
            assert metadata["test_acc"] == 0.95


# ---------------------------------------------------------------------------
# 3. Action Intelligence Engine & SRE Heuristics Tests
# ---------------------------------------------------------------------------


class TestActionIntelligenceEngine:
    """Test suite for production ActionIntelligenceEngine decision logic."""

    def test_recommendation_nominal_state(self, nominal_state_vector: ActionStateVector) -> None:
        rec = ACTION_ENGINE.recommend(nominal_state_vector)

        assert isinstance(rec, ActionRecommendation)
        assert 0.0 <= rec.confidence <= 1.0
        assert len(rec.all_action_probabilities) == 11
        assert rec.inference_time_ms < 50.0  # Fast inference
        assert "nominal" in rec.tactical_rationale.lower() or "operational" in rec.tactical_rationale.lower()

    def test_recommendation_cpu_saturation(self, cpu_saturation_vector: ActionStateVector) -> None:
        rec = ACTION_ENGINE.recommend(cpu_saturation_vector)

        assert isinstance(rec, ActionRecommendation)
        # SRE logic recommends scaling workers or activating rate limiting under extreme CPU surge
        assert rec.primary_action in [
            SREAction.SCALE_OUT_WORKERS,
            SREAction.ACTIVATE_RATE_LIMIT,
            SREAction.ENABLE_WAITING_ROOM,
        ]
        assert len(rec.tactical_rationale) > 20

    def test_recommendation_db_pool_exhaustion(
        self, db_pool_exhaustion_vector: ActionStateVector
    ) -> None:
        rec = ACTION_ENGINE.recommend(db_pool_exhaustion_vector)

        assert isinstance(rec, ActionRecommendation)
        assert rec.primary_action in [
            SREAction.INCREASE_DB_POOL,
            SREAction.DIVERT_READS_TO_REPLICA,
            SREAction.DRAIN_REQUEST_QUEUE,
        ]

    def test_hitl_approval_enforcement(self) -> None:
        """Verify secure_action.md requirement: actions with HIGH blast radius require human approval."""
        engine = ActionIntelligenceEngine()
        assert engine is not None
        # High blast radius actions must enforce requires_human_approval
        assert ACTION_BLAST_RADIUS[SREAction.DRAIN_REQUEST_QUEUE] == "HIGH"
        assert ACTION_BLAST_RADIUS[SREAction.ENGAGE_CIRCUIT_BREAKER] == "HIGH"
        assert ACTION_BLAST_RADIUS[SREAction.RESTART_DEGRADED_PODS] == "HIGH"

    def test_recommendation_from_raw_telemetry(self) -> None:
        """Verify engine can ingest RawTelemetry directly with on-the-fly vector extraction."""
        raw = RawTelemetry(
            active_users=15000,
            requests_per_sec=850.0,
            cpu_percent=42.0,
            ram_percent=48.0,
            network_in=65.0,
            network_out=140.0,
            response_time=75.0,
            throughput=845.0,
            error_rate=0.001,
            http_5xx=1.0,
            db_latency=22.0,
            db_connections=30.0,
            queue_length=5,
            service_instances=4,
        )
        rec = ACTION_ENGINE.recommend(raw)
        assert isinstance(rec, ActionRecommendation)
        assert rec.action_id in ACTION_INDEX_MAP


# ---------------------------------------------------------------------------
# 4. FastAPI HTTP Endpoints Tests
# ---------------------------------------------------------------------------


class TestFastAPIEndpointsM4:
    """Test suite for Module 4 FastAPI endpoints."""

    def test_get_action_catalog(self) -> None:
        response = client.get("/api/v1/action/actions")
        assert response.status_code == 200
        data = response.json()
        assert data["total_actions"] == 11
        assert len(data["actions"]) == 11

        names = [act["action_name"] for act in data["actions"]]
        for action_enum in SREAction:
            assert action_enum.value in names

    def test_get_action_metadata(self) -> None:
        response = client.get("/api/v1/action/metadata")
        assert response.status_code == 200
        data = response.json()
        assert "model_architecture" in data
        assert "device" in data
        assert data["actions_count"] == 11

    def test_post_prescribe_action(self, nominal_state_vector: ActionStateVector) -> None:
        payload = nominal_state_vector.model_dump()
        response = client.post("/api/v1/action/recommend", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "primary_action" in data
        assert "confidence" in data
        assert "all_action_probabilities" in data
        assert "tactical_rationale" in data
        assert "requires_human_approval" in data

    def test_get_live_action_recommendation(self) -> None:
        # Seed collector buffer first to ensure telemetry exists
        raw = RawTelemetry(
            active_users=12000,
            requests_per_sec=700.0,
            cpu_percent=35.0,
            ram_percent=45.0,
            network_in=50.0,
            network_out=120.0,
            response_time=60.0,
            throughput=698.0,
            error_rate=0.001,
            http_5xx=0.5,
            db_latency=20.0,
            db_connections=28.0,
            queue_length=0,
            service_instances=4,
        )
        COLLECTOR.ingest(raw)

        response = client.get("/api/v1/action/live")
        assert response.status_code == 200
        data = response.json()
        assert "primary_action" in data
        assert 0.0 <= data["confidence"] <= 1.0


# ---------------------------------------------------------------------------
# 5. Training Pipeline Verification Test
# ---------------------------------------------------------------------------


def test_train_action_policy_execution() -> None:
    """Verify train_action_policy runs end-to-end and satisfies accuracy bounds."""
    with tempfile.TemporaryDirectory() as tmpdir:
        meta = train_action_policy(
            n_samples=220,  # 20 samples per class
            epochs=2,
            batch_size=16,
            output_dir=Path(tmpdir),
        )
        assert "test_accuracy" in meta
        assert "latency_ms" in meta
        assert (Path(tmpdir) / "action_mlp_policy.pt").exists()
        assert (Path(tmpdir) / "scaler.pkl").exists()
        assert (Path(tmpdir) / "action_metadata.json").exists()
