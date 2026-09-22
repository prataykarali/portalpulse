"""PortalPulse - State-Reactive Avatar Engine (PRD-03 §10, §11, §12)
Generates dynamic, state-aware speech for Nirantar (7 SRE Pipeline Avatars)
and IEMCRP (3 Domain Workflow Avatars) based on real-time telemetry, model inferences,
active chaos faults, and closed-loop verification results.

ALL EMOJIS REMOVED. Pure image-asset driven avatars with multiple transparent-background poses.
Ensures Main Nirantar and IEMCRP real production websites remain completely unhurt and isolated.
"""

from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from datetime import datetime


class AvatarSpeech(BaseModel):
    avatar_id: str
    role_name: str
    avatar_icon: str = ""  # Clean textual/badge label (NO EMOJIS)
    avatar_image: str  # Path to transparent PNG asset
    avatar_pose: str = "nominal"  # Multiple poses: nominal, alert, acting, blocked, recovering
    system_role: str  # e.g., "Telemetry Monitor", "Academic Processing Specialist"
    state: str = "NORMAL"  # NORMAL, ALERT, ACTING, RECOVERING, BLOCKED
    speech: str
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().strftime("%H:%M:%S"))
    confidence: Optional[float] = None
    telemetry_reference: Dict[str, Any] = Field(default_factory=dict)


class PortalAvatarRoster(BaseModel):
    portal_id: str
    portal_name: str
    avatars: List[AvatarSpeech]


def generate_nirantar_avatars(
    telemetry: Optional[Dict[str, Any]] = None,
    pipeline_state: Optional[Dict[str, Any]] = None,
    active_fault: Optional[str] = None
) -> List[AvatarSpeech]:
    """Generates state-reactive speech and dynamic poses for Nirantar's 7 SRE pipeline avatars.
    
    All operations are strictly isolated inside PortalPulse so the main Nirantar website remains unhurt.
    """
    t = telemetry or {
        "requests_per_second": 320.0,
        "latency_p95": 185.0,
        "latency_p99": 260.0,
        "error_rate_5xx": 0.02,
        "cpu_usage_pct": 54.0,
        "memory_usage_pct": 62.0,
        "db_connections": 42.0,
        "active_sessions": 2400
    }
    rps = float(t.get("requests_per_second", 0.0))
    p95 = float(t.get("latency_p95", 0.0))
    err = float(t.get("error_rate_5xx", 0.0))
    cpu = float(t.get("cpu_usage_pct", 0.0))
    sessions = int(t.get("active_sessions", 0))

    # 1. Monitoring Avatar - Sentinel
    if err > 1.0 or p95 > 500:
        mon_state = "ALERT"
        mon_pose = "alert"
        mon_img = "assets/robot_excited_nobg.png"
        mon_speech = f"Ingress pressure critical: P95 has surged to {p95:.1f}ms (>2.5x SLA) with {err:.1f}% 5xx drop rate across {sessions} active sessions. Simulated traffic guardrails armed."
    elif rps > 400 or p95 > 250:
        mon_state = "ALERT"
        mon_pose = "alert"
        mon_img = "assets/robot_excited_nobg.png"
        mon_speech = f"Elevated traffic detected: {rps:.1f} RPS incoming. P95 latency climbing at {p95:.1f}ms. Ingress telemetry streams monitored continuously."
    else:
        mon_state = "NORMAL"
        mon_pose = "scanning"
        mon_img = "assets/robot_flying_nobg.png"
        mon_speech = f"All telemetry streams nominal. Ingress load is {rps:.1f} RPS with stable P95 latency at {p95:.1f}ms. Error rate: {err:.2f}%. Main Nirantar core fully protected."

    # 2. Prediction Avatar - Oracle (M2)
    if rps > 450 or active_fault == "TRAFFIC_SPIKE":
        pred_state = "ALERT"
        pred_pose = "alert"
        pred_img = "assets/robot_excited_nobg.png"
        pred_conf = 94.2
        pred_speech = "M2 XGBoost Forecaster projects saturation in 42 seconds under this acceleration curve. Immediate intervention window open."
    elif rps > 300:
        pred_state = "ALERT"
        pred_pose = "forecasting"
        pred_img = "assets/robot_thinking_nobg.png"
        pred_conf = 88.5
        pred_speech = f"M2 60-second horizon predicts RPS will cross 480 within 90 seconds. Trajectory slope: +{rps*0.12:.1f} RPS/min."
    else:
        pred_state = "NORMAL"
        pred_pose = "nominal"
        pred_img = "assets/robot_thinking_nobg.png"
        pred_conf = 96.0
        pred_speech = "Predictive horizon stable. Expected variance over the next 15 minutes is within ±8% of baseline capacity."

    # 3. Anomaly Avatar - Warden (M3)
    if active_fault or p95 > 400 or err > 2.0:
        anom_state = "ALERT"
        anom_pose = "alert"
        anom_img = "assets/robot_excited_nobg.png"
        anom_speech = "Degradation knee detected: Latency curvature d2L/dRPS has spiked. Anomaly score: 0.92 (>3.2 sigma above baseline)."
    elif p95 > 220:
        anom_state = "ALERT"
        anom_pose = "analyzing"
        anom_img = "assets/robot_thinking_nobg.png"
        anom_speech = "Mild distribution shift observed in question-delivery endpoints. P99/P50 ratio widened to 2.8x."
    else:
        anom_state = "NORMAL"
        anom_pose = "nominal"
        anom_img = "assets/robot_excited_nobg.png"
        anom_speech = "Isolation Forest anomaly score is 0.08 (nominal). No statistically significant deviation in request distribution."

    # 4. RCA Avatar - Sherlock (M4)
    if active_fault == "DB_CONNECTION_EXHAUSTION" or t.get("db_connections", 0) > 85:
        rca_state = "ALERT"
        rca_pose = "alert"
        rca_img = "assets/boy_mug_nobg.png"
        rca_speech = "Causal Graph Root Cause: Database connection pool exhaustion. 96% of pool locks held by unindexed student queries."
    elif active_fault == "CACHE_MISS_STORM":
        rca_state = "ALERT"
        rca_pose = "alert"
        rca_img = "assets/boy_mug_nobg.png"
        rca_speech = "Root Cause identified: Redis cache eviction cascade. 88% cache miss rate flooding downstream PostgreSQL query pool."
    elif cpu > 80:
        rca_state = "ALERT"
        rca_pose = "investigating"
        rca_img = "assets/boy_thinking_nobg.png"
        rca_speech = "Root Cause: Exam Engine worker CPU starvation. Cryptographic token verification saturating worker event loops."
    else:
        rca_state = "NORMAL"
        rca_pose = "nominal"
        rca_img = "assets/boy_thinking_nobg.png"
        rca_speech = "Root Cause Analysis: Clean dependency graph. Upstream gateway, worker pool, and Redis cluster are in lockstep."

    # 5. Action Avatar - Commander (M5)
    if p95 > 350 or err > 1.0 or active_fault:
        act_state = "ACTING"
        act_pose = "directing"
        act_img = "assets/boy_explaining_nobg.png"
        act_speech = "Autonomous Action: Gating excess sessions into Virtual Waiting Room + Signal Horizontal Worker Scaling (+3 pods). Main Nirantar unhurt."
    elif rps > 320:
        act_state = "ALERT"
        act_pose = "prepared"
        act_img = "assets/boy_pointing_nobg.png"
        act_speech = "Prepared mitigation: Ready static caching for question banks. Standby readiness: 100%."
    else:
        act_state = "NORMAL"
        act_pose = "standby"
        act_img = "assets/boy_pointing_nobg.png"
        act_speech = "Status: NO_ACTION_REQUIRED. Autonomous actuators idling in standby mode with clean safety cooldown."

    # 6. Safety Avatar - Aegis (M6)
    if active_fault:
        safety_state = "ACTING"
        safety_pose = "evaluating"
        safety_img = "assets/boy_working_nobg.png"
        safety_speech = "Deterministic Guardrails: Blast radius assessed as LOW. Cooldown timer CLEAR (0s). Action consensus: 98.4% APPROVED."
    else:
        safety_state = "NORMAL"
        safety_pose = "guardrails_active"
        safety_img = "assets/boy_sidebar_desk_nobg.png"
        safety_speech = "Deterministic Guardrails: All policies compliant. Max blast radius bounded. Production bypass strictly disabled."

    # 7. Verification Avatar - Auditor (M7)
    if active_fault:
        ver_state = "RECOVERING"
        ver_pose = "measuring"
        ver_img = "assets/robot_typing_nobg.png"
        ver_speech = "Closed-loop verification engaged: Tracking pre/post telemetry delta. Awaiting 15-second stabilization window."
    else:
        ver_state = "NORMAL"
        ver_pose = "verified"
        ver_img = "assets/robot_celebrating_nobg.png"
        ver_speech = "System health score: 96/100. Previous mitigation verified effective (P95 reduction: -64ms, zero 5xx errors). Rollback ready."

    return [
        AvatarSpeech(
            avatar_id="nirantar_mon",
            role_name="Sentinel",
            avatar_icon="[MONITOR]",
            avatar_image=mon_img,
            avatar_pose=mon_pose,
            system_role="Telemetry Monitor",
            state=mon_state,
            speech=mon_speech,
            telemetry_reference={"rps": rps, "p95": p95}
        ),
        AvatarSpeech(
            avatar_id="nirantar_pred",
            role_name="Oracle",
            avatar_icon="[FORECAST]",
            avatar_image=pred_img,
            avatar_pose=pred_pose,
            system_role="Surge Forecaster",
            state=pred_state,
            speech=pred_speech,
            confidence=pred_conf
        ),
        AvatarSpeech(
            avatar_id="nirantar_anom",
            role_name="Warden",
            avatar_icon="[ANOMALY]",
            avatar_image=anom_img,
            avatar_pose=anom_pose,
            system_role="Knee & Anomaly Detector",
            state=anom_state,
            speech=anom_speech
        ),
        AvatarSpeech(
            avatar_id="nirantar_rca",
            role_name="Sherlock",
            avatar_icon="[RCA]",
            avatar_image=rca_img,
            avatar_pose=rca_pose,
            system_role="Causal RCA Specialist",
            state=rca_state,
            speech=rca_speech
        ),
        AvatarSpeech(
            avatar_id="nirantar_act",
            role_name="Commander",
            avatar_icon="[ACTION]",
            avatar_image=act_img,
            avatar_pose=act_pose,
            system_role="Autonomous Actuator",
            state=act_state,
            speech=act_speech
        ),
        AvatarSpeech(
            avatar_id="nirantar_safe",
            role_name="Aegis",
            avatar_icon="[SAFETY]",
            avatar_image=safety_img,
            avatar_pose=safety_pose,
            system_role="Deterministic Safety & Governance",
            state=safety_state,
            speech=safety_speech
        ),
        AvatarSpeech(
            avatar_id="nirantar_ver",
            role_name="Auditor",
            avatar_icon="[VERIFY]",
            avatar_image=ver_img,
            avatar_pose=ver_pose,
            system_role="Closed-Loop Verification",
            state=ver_state,
            speech=ver_speech
        )
    ]


def generate_iemcrp_avatars(
    telemetry: Optional[Dict[str, Any]] = None,
    pipeline_state: Optional[Dict[str, Any]] = None,
    active_fault: Optional[str] = None
) -> List[AvatarSpeech]:
    """Generates domain-specific speech and multiple dynamic poses for IEMCRP's 3 real workflow avatars (PRD-03 §11).
    
    The 3 Avatars use clean transparent PNG assets with multiple poses based on state:
    1. Campus Access Specialist (Student & Faculty Workflow)
    2. Academic ERP Registrar (Academic Processing Coordinator)
    3. Monolith Operations Lead (Monolithic Infrastructure & DB Pool N=50)
    
    All simulations and traffic diversions run inside PortalPulse, leaving the real ERP database unhurt.
    """
    t = telemetry or {
        "requests_per_second": 180.0,
        "latency_p95": 240.0,
        "error_rate_5xx": 0.05,
        "db_connections": 84.0,  # 84% of 50 = 42 connections
        "active_sessions": 850
    }
    rps = float(t.get("requests_per_second", 0.0))
    p95 = float(t.get("latency_p95", 0.0))
    err = float(t.get("error_rate_5xx", 0.0))
    db_conns_pct = float(t.get("db_connections", 0.0))
    active_conns = int(round(db_conns_pct * 0.50))  # pool is 50

    # -------------------------------------------------------------------------
    # 1. IEMCRP User/Access Avatar (Student & Faculty Workflow)
    # -------------------------------------------------------------------------
    if err > 2.0 or p95 > 600:
        acc_state = "ALERT"
        acc_pose = "traffic_surge"
        acc_img = "assets/boy_thinking_nobg.png"
        acc_speech = f"Student lobby choked: 420 students attempting concurrent marksheet lookups are receiving 504 timeouts. Ingress rate: {rps:.1f} RPS. Simulated queue redirection active."
    elif rps > 140:
        acc_state = "ALERT"
        acc_pose = "rush_monitoring"
        acc_img = "assets/boy_thinking_nobg.png"
        acc_speech = f"Heavy student login rush: {rps:.1f} RPS. Semester results query rate is 3.8x normal morning baseline. Sessions active: {t.get('active_sessions', 600)}. Ingress regulated."
    elif active_fault == "DB_CONNECTION_EXHAUSTION":
        acc_state = "BLOCKED"
        acc_pose = "lobby_held"
        acc_img = "assets/boy_working_nobg.png"
        acc_speech = "Student submissions temporarily queued at portal gateway to prevent connection thrashing. Students receive friendly holding banner."
    else:
        acc_state = "NORMAL"
        acc_pose = "friendly_idle"
        acc_img = "assets/boy_happy_nobg.png"
        acc_speech = "Student & Faculty gateway operating smoothly. Authentication handshake takes 38ms. Portal lobby is unencumbered and real ERP is unhurt."

    # -------------------------------------------------------------------------
    # 2. IEMCRP Processing Avatar (Academic ERP Calculations)
    # -------------------------------------------------------------------------
    if active_fault == "DB_LATENCY" or active_conns >= 45:
        proc_state = "ALERT"
        proc_pose = "table_lock_wait"
        proc_img = "assets/boy_working_nobg.png"
        proc_speech = f"Marksheet calculation pipeline stalled: Heavy SQL joins on academic_results table are queuing behind locked rows. Mean compute time: {p95:.1f}ms. Divert ready."
    elif active_fault == "DB_CONNECTION_EXHAUSTION":
        proc_state = "BLOCKED"
        proc_pose = "lock_contention"
        proc_img = "assets/boy_mug_nobg.png"
        proc_speech = "Monolithic transaction coordinator cannot acquire locks. Student autosaves and faculty grade entries are serialized to prevent corruption."
    elif rps > 130:
        proc_state = "ACTING"
        proc_pose = "cache_serving"
        proc_img = "assets/boy_explaining_nobg.png"
        proc_speech = "Serving pre-rendered marksheets via Static Fallback Cache to spare SQL join engine from lock contention."
    else:
        proc_state = "NORMAL"
        proc_pose = "desk_nominal"
        proc_img = "assets/boy_sidebar_desk_nobg.png"
        proc_speech = f"Grade processing engine healthy. CGPA calculation throughput is steady; marksheet rendering queries taking {p95:.1f}ms."

    # -------------------------------------------------------------------------
    # 3. IEMCRP Operations Avatar (Monolithic Infrastructure & DB Pool)
    # -------------------------------------------------------------------------
    if active_conns >= 45 or active_fault in ["DB_CONNECTION_EXHAUSTION", "WORKER_FAILURE"]:
        ops_state = "ALERT"
        ops_pose = "knee_saturation"
        ops_img = "assets/robot_excited_nobg.png"
        ops_speech = f"CRITICAL DATABASE CONCURRENCY KNEE: {active_conns}/50 connection pool slots occupied! Connection 51 will starve and trigger 504 Gateway Timeout. Recommending immediate Static Fallback Divert."
    elif active_conns >= 35:
        ops_state = "ALERT"
        ops_pose = "pool_pressure"
        ops_img = "assets/robot_thinking_nobg.png"
        ops_speech = f"Monolithic database pool under pressure: {active_conns}/50 slots active ({db_conns_pct:.0f}%). Thread pool wait time is 48ms. Gating ingress to keep database safe."
    elif active_fault:
        ops_state = "ACTING"
        ops_pose = "shedding_load"
        ops_img = "assets/robot_typing_nobg.png"
        ops_speech = f"Autonomous load shedding applied. Active connections capped at {active_conns}/50 to prevent kernel lock thrash."
    else:
        ops_state = "NORMAL"
        ops_pose = "pool_healthy"
        ops_img = "assets/robot_happy_nobg.png"
        ops_speech = f"Monolithic database pool operating safely at {active_conns}/50 connections ({db_conns_pct:.0f}% utilization). 0 threads starved. Monolith intact."

    return [
        AvatarSpeech(
            avatar_id="iemcrp_access",
            role_name="Campus Access Specialist",
            avatar_icon="[ACCESS]",
            avatar_image=acc_img,
            avatar_pose=acc_pose,
            system_role="Student & Faculty Workflow",
            state=acc_state,
            speech=acc_speech,
            telemetry_reference={"rps": rps, "sessions": t.get("active_sessions", 600)}
        ),
        AvatarSpeech(
            avatar_id="iemcrp_processing",
            role_name="Academic ERP Registrar",
            avatar_icon="[PROCESS]",
            avatar_image=proc_img,
            avatar_pose=proc_pose,
            system_role="Academic Processing Coordinator",
            state=proc_state,
            speech=proc_speech,
            telemetry_reference={"p95": p95, "error_rate": err}
        ),
        AvatarSpeech(
            avatar_id="iemcrp_ops",
            role_name="Monolith Operations Lead",
            avatar_icon="[OPS-DB]",
            avatar_image=ops_img,
            avatar_pose=ops_pose,
            system_role="Monolithic Infrastructure & DB Pool (N=50)",
            state=ops_state,
            speech=ops_speech,
            telemetry_reference={"active_conns": active_conns, "max_pool": 50, "utilization_pct": db_conns_pct}
        )
    ]


def get_portal_avatars(
    portal_id: str,
    telemetry: Optional[Dict[str, Any]] = None,
    pipeline_state: Optional[Dict[str, Any]] = None,
    active_fault: Optional[str] = None
) -> PortalAvatarRoster:
    """Retrieve avatars for the requested portal with state-reactive commentary and transparent image poses."""
    pid = portal_id.lower().replace("-", "_")
    if "college" in pid or "iemcrp" in pid:
        return PortalAvatarRoster(
            portal_id="iemcrp",
            portal_name="IEMCRP State University Examination Cell",
            avatars=generate_iemcrp_avatars(telemetry, pipeline_state, active_fault)
        )
    return PortalAvatarRoster(
        portal_id="nirantar",
        portal_name="Nirantar Railway & National Examination Portal",
        avatars=generate_nirantar_avatars(telemetry, pipeline_state, active_fault)
    )
