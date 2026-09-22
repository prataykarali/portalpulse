"""
tests/test_module9_trajectory.py
Comprehensive test suite for Module 9: Actuator Stabilization Trajectory
Validates:
1. 5-state stabilization trajectory: PRE-ACTION -> CRITICAL -> ACTUATING -> STABILIZING -> NOMINAL
2. 6 required metrics in ActuationRecord deltas and trajectory:
   CPU, latency, DB utilization, queue depth, RPS, error rate
3. Before, during, and after metric tracking and relief percentages without invented values
4. ControlCycle actuation broadcast payload enrichment
5. Web UI elements in website/index.html and website/style.css
6. No alert() usage in website/index.html and website/app.js
"""

import os
import re
import pytest
from backend.m7_actuator.actuator import CLOSED_LOOP_ACTUATOR
from backend.m7_actuator.schema import ActuationRecord, ActuationRequest
from backend.m4_action_intelligence.schema import SREAction
from backend.control_plane.control_loop import ControlCycle
from backend.streaming.broadcaster import STREAM_BROADCASTER


def test_actuator_5_state_stabilization_trajectory():
    """Verify actuator returns all 5 canonical trajectory states."""
    req = ActuationRequest(
        action=SREAction.ENABLE_WAITING_ROOM,
        portal_id="iemcrp",
        operator_id="operator_test",
        bypass_safety=True,
    )
    record = CLOSED_LOOP_ACTUATOR.execute_action(req)

    assert isinstance(record, ActuationRecord)
    traj = record.stabilization_trajectory
    assert len(traj) == 5, f"Expected 5 trajectory states, got {len(traj)}"

    expected_states = ["PRE-ACTION", "CRITICAL", "ACTUATING", "STABILIZING", "NOMINAL"]
    actual_states = [step["state"] for step in traj]
    assert actual_states == expected_states, f"Trajectory states mismatch: {actual_states}"

    for i, step in enumerate(traj):
        assert step["step"] == i
        # All 6 metrics must be in trajectory
        for m in ["cpu", "latency", "db_utilization", "queue_depth", "rps", "error_rate"]:
            assert m in step, f"Metric '{m}' missing in step {i} ({step['state']})"
            assert isinstance(step[m], (int, float))


def test_actuator_metric_deltas_all_six_metrics():
    """Verify deltas include all 6 required metrics with before, after, and change_percent."""
    req = ActuationRequest(
        action=SREAction.ENABLE_WAITING_ROOM,
        portal_id="iemcrp",
        operator_id="operator_test",
        bypass_safety=True,
    )
    record = CLOSED_LOOP_ACTUATOR.execute_action(req)

    deltas = record.metric_deltas
    assert len(deltas) >= 6

    delta_map = {d.metric_name: d for d in deltas}
    required_metrics = [
        "cpu_percent",
        "response_time_ms",
        "db_connections",
        "queue_length",
        "requests_per_sec",
        "error_rate",
    ]

    for req_name in required_metrics:
        assert req_name in delta_map, f"Required metric '{req_name}' missing from metric_deltas"
        d = delta_map[req_name]
        assert hasattr(d, "before")
        assert hasattr(d, "after")
        assert hasattr(d, "change_percent")
        assert isinstance(d.before, (int, float))
        assert isinstance(d.after, (int, float))
        assert isinstance(d.change_percent, (int, float))
        # After Waiting Room or mitigation, error rate and latency should improve (negative change)
        if req_name in ["response_time_ms", "queue_length", "error_rate"]:
            assert d.after <= d.before, f"Expected {req_name} to decrease after mitigation"


def test_control_cycle_actuation_payload():
    """Verify ControlCycle populates actuation, trajectory, and deltas."""
    from backend.control_plane.explainable_pipeline import EXPLAINABLE_PIPELINE

    cycle = EXPLAINABLE_PIPELINE.run_cycle(portal_id="iemcrp")
    assert isinstance(cycle, ControlCycle)
    cycle_dict = cycle.model_dump()

    assert "stabilization_trajectory" in cycle_dict
    assert "metric_deltas" in cycle_dict
    assert "recovery_state" in cycle_dict
    assert "verification_status" in cycle_dict
    assert cycle.portal_id == "iemcrp"
    assert isinstance(cycle_dict["stabilization_trajectory"], list)
    assert isinstance(cycle_dict["metric_deltas"], list)


def test_web_ui_actuator_panel_elements():
    """Verify website/index.html has all required Module 9 elements."""
    html_path = os.path.join(os.path.dirname(__file__), "..", "website", "index.html")
    with open(html_path, "r", encoding="utf-8") as f:
        html = f.read()

    # Required main panel
    assert 'id="lrActuatorPanel"' in html

    # Intervention summary elements
    assert 'id="lrInterventionSummary"' in html
    assert 'id="lrActAction"' in html
    assert 'id="lrActWhy"' in html
    assert 'id="lrActConf"' in html
    assert 'id="lrActBeforeP95"' in html
    assert 'id="lrActBeforeQueue"' in html
    assert 'id="lrActBeforeDb"' in html
    assert 'id="lrActPhase"' in html
    assert 'id="lrActAfterP95"' in html
    assert 'id="lrActAfterQueue"' in html
    assert 'id="lrActAfterDb"' in html

    # 5-State Trajectory Stepper
    assert 'id="lrTrajectoryStepper"' in html
    assert 'id="lrStepPreAction"' in html
    assert 'id="lrStepCritical"' in html
    assert 'id="lrStepActuating"' in html
    assert 'id="lrStepStabilizing"' in html
    assert 'id="lrStepNominal"' in html
    assert 'id="lrTrajVal0"' in html
    assert 'id="lrTrajVal4"' in html

    # 6 Metrics Table with before, during, after, relief
    assert 'id="lrMetricsTable"' in html
    assert 'id="mBeforeCpu"' in html and 'id="mDuringCpu"' in html and 'id="mAfterCpu"' in html and 'id="mReliefCpu"' in html
    assert 'id="mBeforeLat"' in html and 'id="mDuringLat"' in html and 'id="mAfterLat"' in html and 'id="mReliefLat"' in html
    assert 'id="mBeforeDb"' in html and 'id="mDuringDb"' in html and 'id="mAfterDb"' in html and 'id="mReliefDb"' in html
    assert 'id="mBeforeQueue"' in html and 'id="mDuringQueue"' in html and 'id="mAfterQueue"' in html and 'id="mReliefQueue"' in html
    assert 'id="mBeforeRps"' in html and 'id="mDuringRps"' in html and 'id="mAfterRps"' in html and 'id="mReliefRps"' in html
    assert 'id="mBeforeErr"' in html and 'id="mDuringErr"' in html and 'id="mAfterErr"' in html and 'id="mReliefErr"' in html

    # Recovery Verified Badge & Meter
    assert 'id="lrRecoveryVerifiedBadge"' in html
    assert 'id="lrRecoveryMeter"' in html
    assert 'RECOVERY VERIFIED' in html

    # Action Timeline & SLA Comparison
    assert 'id="lrActionTimelineList"' in html
    assert 'id="lrTimelineCycle"' in html
    assert 'id="lrSlaCard"' in html
    assert 'id="lrSlaLatency"' in html
    assert 'id="lrSlaDb"' in html
    assert 'id="lrSlaError"' in html
    assert 'id="lrSlaAvail"' in html


def test_no_alert_in_frontend():
    """Verify zero alert() invocations exist in website/index.html and website/app.js."""
    website_dir = os.path.join(os.path.dirname(__file__), "..", "website")
    for fname in ["index.html", "app.js"]:
        fpath = os.path.join(website_dir, fname)
        with open(fpath, "r", encoding="utf-8") as f:
            content = f.read()
        # Ensure no alert(...) calls exist
        alerts = re.findall(r'(?<![a-zA-Z0-9_])alert\(', content)
        assert len(alerts) == 0, f"Found alert() in {fname}: {alerts}"


def test_styles_exist_for_actuator_panel():
    """Verify website/style.css defines styling for actuator components."""
    css_path = os.path.join(os.path.dirname(__file__), "..", "website", "style.css")
    with open(css_path, "r", encoding="utf-8") as f:
        css = f.read()

    assert ".lr-actuator-panel" in css
    assert ".lr-intervention-summary" in css
    assert ".lr-trajectory-stepper" in css
    assert ".traj-step" in css
    assert ".lr-metrics-table" in css
    assert ".lr-recovery-badge" in css
    assert ".lr-action-timeline-card" in css
    assert ".lr-sla-comparison-card" in css
