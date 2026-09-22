"""PRD-03: Explainable Autonomous SRE Pipeline, Portal Anatomy & Avatar Engine tests.

Covers:
  - Explainable Pipeline: Full M1-M7 cycle execution, capacity certificate generation,
    consensus detection, verification status, and actuator environment reporting.
  - Portal Anatomy: Nirantar microservices DAG, IEMCRP monolithic DAG with SEVERE bottleneck.
  - Avatar Engine: Nirantar 7 avatars, IEMCRP 3 avatars, state reactivity under faults.
"""

import pytest


# ── Explainable Pipeline ──────────────────────────────────────────────

def test_pipeline_cycle_executes_all_seven_models():
    """A full cycle must produce records for M1 through M7 + VERIFY."""
    from backend.control_plane.explainable_pipeline import ExplainablePipelineEngine

    engine = ExplainablePipelineEngine()
    cycle = engine.run_cycle("nirantar")

    assert cycle.portal_id == "nirantar"
    for model_id in ("M1", "M2", "M3", "M4", "M5", "M6", "M7"):
        assert model_id in cycle.models, f"Missing model stage {model_id}"
        rec = cycle.models[model_id]
        assert rec.status in ("COMPLETE", "SKIPPED")
        assert rec.inference_time_ms >= 0
        assert rec.provenance == "LIVE_MODEL"
    # Verification stage should also exist
    assert "VERIFY" in cycle.models


def test_pipeline_cycle_records_consensus_and_safety():
    """Cycle must report consensus state and safety decision."""
    from backend.control_plane.explainable_pipeline import ExplainablePipelineEngine

    engine = ExplainablePipelineEngine()
    cycle = engine.run_cycle("nirantar")

    assert cycle.consensus_state in (
        "STRONG_CONSENSUS", "DIVERGENT_DISAGREEMENT", "NOMINAL"
    )
    assert cycle.safety_decision in (
        "APPROVED", "REJECTED", "NO_ACTION_REQUIRED", "HITL_REQUIRED"
    )
    assert cycle.actuation_status in ("EXECUTED", "SKIPPED", "ROLLED_BACK")
    assert cycle.actuator_env in ("KUBERNETES", "DOCKER_COMPOSE", "LOCAL_PROCESS")


def test_capacity_certificate_generation():
    """Capacity certificates must contain all required fields and persist in engine."""
    from backend.control_plane.explainable_pipeline import ExplainablePipelineEngine

    engine = ExplainablePipelineEngine()

    for pid in ("nirantar", "iemcrp"):
        cert = engine.generate_capacity_certificate(pid)
        assert cert.portal_id == pid
        assert cert.sustainable_capacity_rps > 0
        assert cert.degradation_knee_rps > cert.sustainable_capacity_rps
        assert cert.hard_saturation_rps > cert.degradation_knee_rps
        assert cert.recommended_headroom_pct > 0
        assert cert.sla_compliance_status in ("PASS", "FAIL")
        assert cert.max_safe_concurrent_users > 0
        assert cert.limiting_bottleneck  # non-empty string
        # Persisted in engine
        assert pid in engine.certificates
        assert engine.certificates[pid] is cert


def test_pipeline_cycle_history():
    """Multiple cycles should be recorded in cycle_history up to cap."""
    from backend.control_plane.explainable_pipeline import ExplainablePipelineEngine

    engine = ExplainablePipelineEngine()
    for _ in range(3):
        engine.run_cycle("nirantar")

    assert len(engine.cycle_history) == 3
    assert engine.last_cycle is engine.cycle_history[-1]


# ── Portal Anatomy ────────────────────────────────────────────────────

def test_nirantar_anatomy_is_microservices():
    """Nirantar anatomy should be MICROSERVICES with >= 6 nodes."""
    from backend.control_plane.portal_anatomy import get_portal_anatomy

    dag = get_portal_anatomy("nirantar")
    assert dag.architecture_type == "MICROSERVICES"
    assert len(dag.nodes) >= 6
    assert len(dag.edges) >= 5
    node_ids = {n.id for n in dag.nodes}
    assert "ingress" in node_ids
    assert "exam_engine" in node_ids


def test_iemcrp_anatomy_monolithic_with_severe_bottleneck():
    """IEMCRP anatomy should be MONOLITHIC with a SEVERE-risk database node."""
    from backend.control_plane.portal_anatomy import get_portal_anatomy

    dag = get_portal_anatomy("iemcrp")
    assert dag.architecture_type == "MONOLITHIC"
    assert len(dag.nodes) >= 4
    # The monolith_db node must have SEVERE bottleneck risk
    db_node = next(n for n in dag.nodes if n.id == "monolith_db")
    assert db_node.bottleneck_risk == "SEVERE"
    assert db_node.metrics["max_pool_size"] == 50
    # At least one bottleneck edge
    bottleneck_edges = [e for e in dag.edges if e.is_bottleneck]
    assert len(bottleneck_edges) >= 1


# ── Avatar Engine ─────────────────────────────────────────────────────

def test_nirantar_produces_seven_avatars():
    """Nirantar should generate exactly 7 SRE pipeline avatars."""
    from backend.control_plane.avatar_engine import get_portal_avatars

    roster = get_portal_avatars("nirantar")
    assert roster.portal_id == "nirantar"
    assert len(roster.avatars) == 7
    role_names = {a.role_name for a in roster.avatars}
    assert "Sentinel" in role_names
    assert "Commander" in role_names


def test_iemcrp_produces_three_avatars():
    """IEMCRP should generate exactly 3 domain avatars."""
    from backend.control_plane.avatar_engine import get_portal_avatars

    roster = get_portal_avatars("iemcrp")
    assert roster.portal_id == "iemcrp"
    assert len(roster.avatars) == 3
    ids = {a.avatar_id for a in roster.avatars}
    assert "iemcrp_access" in ids
    assert "iemcrp_processing" in ids
    assert "iemcrp_ops" in ids


def test_avatar_state_reacts_to_fault():
    """Avatars must shift to ALERT/BLOCKED state when a fault is active."""
    from backend.control_plane.avatar_engine import get_portal_avatars

    # Inject a DB exhaustion fault signal
    roster = get_portal_avatars(
        "iemcrp",
        telemetry={
            "requests_per_second": 200.0,
            "latency_p95": 800.0,
            "error_rate_5xx": 5.0,
            "db_connections": 96.0,  # 96% of 50
            "active_sessions": 1200
        },
        active_fault="DB_CONNECTION_EXHAUSTION"
    )
    states = {a.avatar_id: a.state for a in roster.avatars}
    # Under heavy fault, at least the ops and processing avatars should not be NORMAL
    assert states["iemcrp_ops"] in ("ALERT", "BLOCKED")
    assert states["iemcrp_processing"] in ("ALERT", "BLOCKED")
    assert states["iemcrp_access"] in ("ALERT", "BLOCKED")


def test_avatars_use_image_assets_and_no_emojis():
    """Avatars must use transparent PNG image assets and contain NO emoji characters."""
    import re
    from backend.control_plane.avatar_engine import get_portal_avatars

    # Regex detecting common emoji ranges
    emoji_pattern = re.compile(r"[\U00010000-\U0010ffff]", flags=re.UNICODE)

    for pid in ("nirantar", "iemcrp"):
        roster = get_portal_avatars(pid)
        for a in roster.avatars:
            # Must point to valid asset
            assert a.avatar_image.startswith("assets/"), f"Avatar {a.role_name} missing valid asset path"
            assert a.avatar_image.endswith("_nobg.png"), f"Avatar {a.role_name} asset must have transparent background (_nobg.png)"
            assert a.avatar_pose, f"Avatar {a.role_name} missing pose definition"

            # Must contain no emojis in role_name or avatar_icon
            assert not emoji_pattern.search(a.role_name), f"Role name {a.role_name} contains emoji"
            assert not emoji_pattern.search(a.avatar_icon), f"Avatar icon {a.avatar_icon} contains emoji"

