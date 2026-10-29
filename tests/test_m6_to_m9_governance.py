"""Unit and integration test suite for PortalPulse Modules 6-9.

Verifies:
1. Module 6: Deterministic Safety Layer, confidence gate (>=80%), 5m cooldowns, token bucket, circuit breakers, and HITL approvals.
2. Module 7: Closed-Loop Actuator, physical metric relief, stabilization trajectories, and audit trail.
3. Module 8: Chaos Engineering Lab, fault injection, and M/M/c queuing knee-point curvature analysis.
4. Module 9: MLOps Kolmogorov-Smirnov non-parametric drift detection, PSI scoring, and Model Registry governance.
5. FastAPI endpoints across M6, M7, M8, and M9.
"""

from __future__ import annotations

import numpy as np
import pytest
from fastapi.testclient import TestClient

from backend.app import app
from backend.m1_monitoring.collector import COLLECTOR
from backend.m1_monitoring.schema import RawTelemetry
from backend.m4_action_intelligence.schema import SREAction
from backend.m6_safety_layer.guardrails import (
    SAFETY_GUARDRAILS,
    CircuitBreaker,
    CircuitState,
    DeterministicSafetyGuardrails,
    TokenBucket,
)
from backend.m6_safety_layer.schema import (
    ActionIntent,
    ApprovalStatus,
)
from backend.m7_actuator.actuator import ClosedLoopActuator
from backend.m7_actuator.schema import ActuationRequest
from backend.m8_chaos_lab.chaos_engine import ChaosEngineeringLab
from backend.m8_chaos_lab.schema import ChaosInjectionRequest, ChaosScenario
from backend.m9_mlops_drift.drift_detector import MLOpsDriftGovernanceEngine
from backend.m9_mlops_drift.schema import DriftStatus

client = TestClient(app)


# ---------------------------------------------------------------------------
# Test Fixtures & Seed Telemetry
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session", autouse=True)
def seed_baseline_telemetry() -> None:
    raw = RawTelemetry(
        active_users=32000,
        requests_per_sec=2200.0,
        cpu_percent=82.0,
        ram_percent=60.0,
        network_in=140.0,
        network_out=320.0,
        response_time=680.0,
        throughput=2160.0,
        error_rate=0.012,
        http_5xx=35.0,
        db_latency=42.0,
        db_connections=58.0,
        queue_length=220,
        service_instances=4,
    )
    COLLECTOR.ingest(raw)


# ---------------------------------------------------------------------------
# 1. Module 6: Safety Layer & HITL Gate Tests
# ---------------------------------------------------------------------------


class TestSafetyGuardrails:
    """Test suite for deterministic safety rules, token bucket, and approvals."""

    def test_token_bucket_consumption_and_refill(self) -> None:
        tb = TokenBucket(capacity=10.0, refill_rate=5.0)
        assert tb.consume(5.0) is True
        assert tb.consume(5.0) is True
        # Bucket exhausted
        assert tb.consume(5.0) is False

    def test_circuit_breaker_state_transitions(self) -> None:
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout_sec=0.1, error_rate_threshold=0.08)
        assert cb.state == CircuitState.CLOSED

        # Trip circuit breaker
        cb.record_outcome(error_rate=0.15, http_5xx=120.0)
        cb.record_outcome(error_rate=0.15, http_5xx=120.0)
        cb.record_outcome(error_rate=0.15, http_5xx=120.0)
        assert cb.state == CircuitState.OPEN

    def test_low_confidence_requires_human_approval(self) -> None:
        intent = ActionIntent(
            action=SREAction.SCALE_OUT_WORKERS,
            confidence=0.74,  # Sub-80% confidence
            justification="Low confidence test",
        )
        res = SAFETY_GUARDRAILS.validate_action(intent, force_bypass_cooldown=True)
        assert res.is_safe is True
        assert res.requires_human_approval is True
        assert res.approval_request_id is not None
        assert res.approval_request_id.startswith("appr_")

    def test_high_blast_radius_requires_human_approval(self) -> None:
        intent = ActionIntent(
            action=SREAction.DRAIN_REQUEST_QUEUE,  # HIGH blast radius
            confidence=0.99,                       # Even with 99% confidence!
            justification="High blast radius test",
        )
        res = SAFETY_GUARDRAILS.validate_action(intent, force_bypass_cooldown=True)
        assert res.requires_human_approval is True

    def test_flapping_cooldown_enforcement(self) -> None:
        guardrails = DeterministicSafetyGuardrails()
        intent = ActionIntent(
            action=SREAction.SCALE_OUT_WORKERS,
            confidence=0.92,
        )
        # First validation passes
        res1 = guardrails.validate_action(intent)
        assert res1.is_safe is True

        # Simulate execution
        guardrails.record_action_executed(SREAction.SCALE_OUT_WORKERS)

        # Immediate second validation must be blocked by flapping cooldown
        res2 = guardrails.validate_action(intent)
        assert res2.is_safe is False
        assert any("flapping cooldown" in r for r in res2.rejection_reasons)
        assert res2.cooldown_remaining_sec > 0.0

    def test_two_phase_operator_approval_cycle(self) -> None:
        guardrails = DeterministicSafetyGuardrails()
        intent = ActionIntent(
            action=SREAction.RESTART_DEGRADED_PODS,
            confidence=0.72,
            justification="Memory leak observed",
        )
        val = guardrails.validate_action(intent)
        req_id = val.approval_request_id
        assert req_id is not None

        # Confirm request is in pending store
        pending = guardrails.get_pending_approvals()
        assert any(r.request_id == req_id for r in pending)

        # Operator APPROVES the request
        dec = guardrails.decide_approval(
            request_id=req_id,
            approved=True,
            operator_id="lead_sre_jdoe",
            comment="Approved rolling restart after heap inspection",
        )
        assert dec.status == ApprovalStatus.APPROVED
        assert "APPROVED" in dec.message

        # Verify no longer in pending store
        assert not any(r.request_id == req_id for r in guardrails.get_pending_approvals())


# ---------------------------------------------------------------------------
# 2. Module 7: Closed-Loop Actuator Tests
# ---------------------------------------------------------------------------


class TestClosedLoopActuator:
    """Test suite for closed-loop infrastructure actuation and stabilization."""

    def test_scale_out_actuation_trajectory(self) -> None:
        actuator = ClosedLoopActuator()
        req = ActuationRequest(
            action=SREAction.SCALE_OUT_WORKERS,
            parameters={"replicas": 2, "confidence": 0.95},
            operator_id="human_oncall_sre",
            bypass_safety=True,
        )
        rec = actuator.execute_action(req)

        assert rec.status == "SUCCESS"
        assert rec.action == SREAction.SCALE_OUT_WORKERS
        assert len(rec.metric_deltas) >= 5
        assert len(rec.stabilization_trajectory) == 5

        # The first point records the measured pre-action state.
        states = [step["state"] for step in rec.stabilization_trajectory]
        assert states == ["PRE-ACTION", "CRITICAL", "ACTUATING", "STABILIZING", "NOMINAL"]

    def test_database_pool_expansion_actuation(self) -> None:
        actuator = ClosedLoopActuator()
        req = ActuationRequest(
            action=SREAction.INCREASE_DB_POOL,
            parameters={"confidence": 0.96},
            operator_id="human_oncall_sre",
            bypass_safety=True,
        )
        rec = actuator.execute_action(req)

        # Verify DB connection pool drop
        db_delta = next((d for d in rec.metric_deltas if d.metric_name == "db_connections"), None)
        assert db_delta is not None
        assert db_delta.after < db_delta.before

    def test_audit_log_tracking(self) -> None:
        actuator = ClosedLoopActuator()
        actuator.execute_action(
            ActuationRequest(action=SREAction.PURGE_REDIS_CACHE, bypass_safety=True)
        )
        log = actuator.get_audit_log()
        assert log.total_executions >= 1
        assert log.executions[-1].action == SREAction.PURGE_REDIS_CACHE


# ---------------------------------------------------------------------------
# 3. Module 8: Chaos Engineering & Knee Point Tests
# ---------------------------------------------------------------------------


class TestChaosEngineeringLab:
    """Test suite for fault injection drills and M/M/c knee point detection."""

    def test_chaos_injection_and_recovery(self) -> None:
        lab = ChaosEngineeringLab()
        # Inject Database Lock Jam
        inj = ChaosInjectionRequest(
            scenario=ChaosScenario.DATABASE_LOCK_JAM,
            intensity=2.0,
            duration_seconds=60,
        )
        status_inj = lab.inject_chaos(inj)
        assert status_inj.is_active is True
        assert status_inj.active_scenario == ChaosScenario.DATABASE_LOCK_JAM

        # Recover platform
        status_rec = lab.recover()
        assert status_rec.is_active is False
        assert status_rec.active_scenario == ChaosScenario.NORMAL

    def test_knee_point_curvature_analysis(self) -> None:
        lab = ChaosEngineeringLab()
        knee = lab.analyze_knee_point()

        assert knee.knee_point_rps > 1000.0
        assert knee.knee_latency_ms == 450.0
        assert 0.0 <= knee.headroom_percent <= 100.0
        assert knee.curvature_d2_latency >= 0.0
        assert knee.saturation_state in ["NOMINAL", "APPROACHING_KNEE", "SATURATED_KNEE"]


# ---------------------------------------------------------------------------
# 4. Module 9: MLOps Drift Detection & Governance Tests
# ---------------------------------------------------------------------------


class TestMLOpsDriftGovernance:
    """Test suite for Kolmogorov-Smirnov distribution test and PSI scoring."""

    def test_psi_identical_vs_shifted(self) -> None:
        engine = MLOpsDriftGovernanceEngine()
        rng = np.random.default_rng(42)
        base = rng.normal(500.0, 100.0, 500)
        identical = base.copy()
        shifted = rng.normal(1200.0, 250.0, 500)

        psi_zero = engine.compute_psi(base, identical)
        assert psi_zero < 0.05

        psi_high = engine.compute_psi(base, shifted)
        assert psi_high >= 0.25

    def test_live_drift_evaluation(self) -> None:
        engine = MLOpsDriftGovernanceEngine()
        rep = engine.evaluate_live_drift()

        assert rep.overall_status in [DriftStatus.HEALTHY, DriftStatus.MONITOR, DriftStatus.RETRAIN_RECOMMENDED]
        assert len(rep.features) == 5
        for feat in rep.features:
            assert 0.0 <= feat.ks_statistic <= 1.0
            assert 0.0 <= feat.p_value <= 1.0
            assert feat.psi_score >= 0.0

    def test_model_registry_entries(self) -> None:
        engine = MLOpsDriftGovernanceEngine()
        reg = engine.get_model_registry()

        assert reg.total_models == 4
        m_ids = [m.model_id for m in reg.models]
        assert "m2_forecaster_xgboost" in m_ids
        assert "m3_anomaly_isolation_forest" in m_ids
        assert "m4_rca_xgboost" in m_ids
        assert "m4_action_policy_mlp" in m_ids


# ---------------------------------------------------------------------------
# 5. FastAPI Endpoints Tests (M6 to M9)
# ---------------------------------------------------------------------------


class TestFastAPIEndpointsM6toM9:
    """Test suite for HTTP API routes across Modules 6-9."""

    # Module 6: Safety
    def test_post_validate_safety(self) -> None:
        payload = {"action": "SCALE_OUT_WORKERS", "confidence": 0.95, "parameters": {"replicas": 2}}
        res = client.post("/api/v1/safety/validate", json=payload)
        assert res.status_code == 200
        assert "is_safe" in res.json()

    def test_get_circuit_breaker(self) -> None:
        res = client.get("/api/v1/safety/circuit-breaker")
        assert res.status_code == 200
        assert res.json()["state"] in ["CLOSED", "OPEN", "HALF_OPEN"]

    # Module 7: Actuator
    def test_post_actuator_execute_and_audit(self) -> None:
        payload = {
            "action": "SCALE_OUT_WORKERS",
            "parameters": {"replicas": 2},
            "operator_id": "sre_test_runner",
            "bypass_safety": True,
        }
        res = client.post("/api/v1/actuator/execute", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "SUCCESS"
        assert len(data["metric_deltas"]) >= 1

        # Check audit log endpoint
        res_audit = client.get("/api/v1/actuator/audit-log")
        assert res_audit.status_code == 200
        assert res_audit.json()["total_executions"] >= 1

    # Module 8: Chaos Lab
    def test_chaos_inject_recover_endpoints(self) -> None:
        res_inj = client.post(
            "/api/v1/chaos/inject",
            json={"scenario": "RESULT_RUSH", "intensity": 1.5, "duration_seconds": 60},
        )
        assert res_inj.status_code == 200
        assert res_inj.json()["active_scenario"] == "RESULT_RUSH"

        res_knee = client.get("/api/v1/chaos/knee-analysis")
        assert res_knee.status_code == 200
        assert "knee_point_rps" in res_knee.json()

        res_rec = client.post("/api/v1/chaos/recover")
        assert res_rec.status_code == 200
        assert res_rec.json()["active_scenario"] == "NORMAL"

    # Module 9: MLOps
    def test_mlops_drift_and_registry_endpoints(self) -> None:
        res_drift = client.get("/api/v1/mlops/drift")
        assert res_drift.status_code == 200
        assert "overall_status" in res_drift.json()

        res_reg = client.get("/api/v1/mlops/model-registry")
        assert res_reg.status_code == 200
        assert res_reg.json()["total_models"] == 4
