"""PortalPulse Production Dashboard — Autonomous Closed-Loop Intelligence & Control Tower.

Features:
- Initial High-Security Login Screen (Student, Faculty, Master Admin via RBAC Access Tokens)
- PortalPulse Control Tower (Live APM, Model Consensus & Uncertainty, MLOps Drift Monitor, Closed-Loop Simulator)
- Prescriptive Capacity Recommendation Engine (Actionable pod & DB pool sizing recommendations)
- Custom Stress Lab & Automated Experiment Mode (Automated Multi-Point Concurrency Sweep & Knee-Point Saturation Detection)
- Real SQLite WAL Persistence, Hybrid Redis Caching & PostgreSQL Enterprise Migration Path
"""

from __future__ import annotations

import base64
import json
import random
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
import sys
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Database & Token Authentication
from dashboard.db import (
    ROLE_ACCESS_TOKENS,
    QUANTUM_KEYS,
    validate_role_access_token,
    validate_quantum_key,
    add_student,
    get_all_faculty,
    get_all_students,
    get_db_stats,
    get_profile,
    get_query_logs,
    get_student_results,
    get_students_by_department,
    init_db,
    run_db_stress_benchmark,
    seed_sample_students,
    update_student_grade,
    DB_ADAPTER,
)

# ML Ensemble, Drift & Closed-Loop Modules
from week2.team2_ml.model_router import MODEL_ROUTER
from week2.team2_ml.drift_detector import DRIFT_DETECTOR
from week2.team1_simulation.protection_controller import PRESCRIPTIVE_ADVISOR, CLOSED_LOOP_CONTROLLER
from week2.team1_simulation.telemetry_synthesizer import synthesize_telemetry as core_synthesize, find_saturation_knee

ASSETS_DIR = ROOT / "dashboard" / "assets"
BANNER_PATH = ASSETS_DIR / "banner.jpg"
MASCOT_PATH = ASSETS_DIR / "mascot.jpg"
CAMPUS_PATH = ASSETS_DIR / "campus.jpg"
SHIELD_PATH = ASSETS_DIR / "shield.jpg"

SLA_LATENCY = 800.0
SLA_CPU = 85.0

SCENARIOS = {
    "Result Declaration Rush": {
        "badge": "High spike traffic · Heavy database joins",
        "description": "Mass simultaneous student logins querying un-cached semester result tables.",
        "typical_users": 8500,
        "is_result": 1,
        "rps_factor": 0.15,
        "knee": 7800,
        "workload": 1.45,
    },
    "Regular Academic Day": {
        "badge": "Stable diurnal traffic · Light cached reads",
        "description": "Routine attendance checks, timetable views, LMS course material downloads.",
        "typical_users": 3200,
        "is_result": 0,
        "rps_factor": 0.12,
        "knee": 9200,
        "workload": 1.0,
    },
    "Exam Fee Registration": {
        "badge": "Sustained high concurrency · DB lock contention",
        "description": "Transactional sessions submitting invoices and payment gateway callbacks.",
        "typical_users": 7600,
        "is_result": 0,
        "rps_factor": 0.135,
        "knee": 8400,
        "workload": 1.25,
    },
    "Course Registration Rush": {
        "badge": "Burst race condition · Seat quota locks",
        "description": "Opening-minute concurrency rush competing for limited elective seats.",
        "typical_users": 8800,
        "is_result": 0,
        "rps_factor": 0.14,
        "knee": 8100,
        "workload": 1.35,
    },
    "Off-Peak Night": {
        "badge": "Low baseline · Background maintenance",
        "description": "Early morning hours with minimal read operations and scheduled backups.",
        "typical_users": 650,
        "is_result": 0,
        "rps_factor": 0.10,
        "knee": 9500,
        "workload": 0.85,
    },
}

NAV_ADMIN = [
    ("Control Tower", "🗼"),
    ("Dashboard", "🏠"),
    ("Simulator", "🚀"),
    ("Custom Stress Lab", "🧪"),
    ("All Accounts Directory", "👥"),
    ("Student Portal & DB", "🎓"),
    ("Faculty Studio", "👨‍🏫"),
    ("Telemetry", "📊"),
    ("Models (ML)", "⚙️"),
    ("Benchmarks (ML)", "🏆"),
    ("Insights", "📈"),
    ("Architecture & Migration", "⚡"),
    ("Reports", "📄"),
]

NAV_FACULTY = [
    ("Faculty Studio", "👨‍🏫"),
]

NAV_STUDENT = [
    ("My Student Portal", "🎓"),
    ("Session Health & Redirect Risk", "🛡️"),
]


def get_image_base64(path: Path) -> str:
    if path.exists():
        return base64.b64encode(path.read_bytes()).decode("utf-8")
    return ""


def calculate_student_redirect_risk(users: int, safe_capacity: float) -> float:
    ratio = users / max(safe_capacity, 1.0)
    risk = (ratio**2.5) * 15.0
    return float(round(np.clip(risk, 1.0, 99.0), 1))


def synthesize_telemetry(
    scenario_name: str,
    users: int,
    num_pods: int = 4,
    db_pool_size: int = 100,
    cache_hit_ratio: float = 0.70,
    waiting_room_enabled: bool = False,
    degraded_mode: bool = False,
    fault_type: str = "None",
    sla_latency: float = SLA_LATENCY,
    sla_cpu: float = SLA_CPU,
) -> dict:
    tel = core_synthesize(
        scenario_name=scenario_name,
        concurrent_users=users,
        num_pods=num_pods,
        db_pool_size=db_pool_size,
        cache_hit_ratio=cache_hit_ratio,
        waiting_room_enabled=waiting_room_enabled,
        degraded_mode=degraded_mode,
        fault_type=fault_type,
        sla_latency=sla_latency,
        sla_cpu=sla_cpu,
    )
    tel["redirect_risk"] = calculate_student_redirect_risk(users, tel["safe_capacity"])
    return tel


def inject_custom_css() -> None:
    st.markdown(
        """
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800;900&display=swap');

html, body, [class*="css"], .stApp {
  font-family: 'Plus Jakarta Sans', -apple-system, sans-serif !important;
  background-color: #F8FAFC !important;
  color: #0F172A;
}

.block-container {
  padding-top: 1.0rem;
  padding-bottom: 2.5rem;
  max-width: 1380px;
}

[data-testid="stSidebar"] {
  background-color: #FFFFFF !important;
  border-right: 1px solid #E2E8F0;
  padding-top: 1rem;
}

.banner-container {
  width: 100%;
  border-radius: 18px;
  overflow: hidden;
  margin-bottom: 18px;
  box-shadow: 0 4px 20px rgba(0,0,0,0.06);
  border: 1px solid #E2E8F0;
}

.banner-container img {
  width: 100%;
  height: 145px;
  object-fit: cover;
  display: block;
}

.header-box {
  background: #FFFFFF;
  border: 1px solid #E2E8F0;
  border-radius: 18px;
  padding: 20px 24px;
  margin-bottom: 20px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  box-shadow: 0 2px 8px rgba(0,0,0,0.02);
}

.header-title h1 {
  font-size: 22px;
  font-weight: 900;
  color: #0F172A;
  margin: 0;
  letter-spacing: -0.02em;
}

.header-title p {
  font-size: 13px;
  color: #64748B;
  margin: 4px 0 0 0;
}

.kpi-container {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 14px;
  margin-bottom: 20px;
}

.kpi-card {
  background: #FFFFFF;
  border: 1px solid #E2E8F0;
  border-radius: 16px;
  padding: 16px 18px;
  box-shadow: 0 2px 6px rgba(0,0,0,0.02);
  transition: transform 0.15s ease;
}

.kpi-card:hover { transform: translateY(-2px); }

.kpi-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  font-weight: 700;
  color: #64748B;
}

.kpi-value {
  font-size: 24px;
  font-weight: 900;
  color: #0F172A;
  margin: 6px 0 2px 0;
  letter-spacing: -0.02em;
}

.kpi-sub { font-size: 11.5px; color: #94A3B8; }

.main-card {
  background: #FFFFFF;
  border: 1px solid #E2E8F0;
  border-radius: 20px;
  padding: 22px 26px;
  box-shadow: 0 2px 10px rgba(0,0,0,0.03);
  height: 100%;
}

.card-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 800;
  color: #0F172A;
  margin-bottom: 4px;
}

.card-subtitle {
  font-size: 12.5px;
  color: #64748B;
  margin-bottom: 14px;
}

.risk-callout {
  border-radius: 18px;
  padding: 24px;
  text-align: center;
  margin: 16px 0;
}

.risk-number {
  font-size: 54px;
  font-weight: 900;
  line-height: 1.1;
}

div.stButton > button {
  width: 100%;
  text-align: left;
  border-radius: 10px;
  font-weight: 700;
  font-size: 13.5px;
  padding: 9px 14px;
  border: 1px solid transparent;
  background-color: transparent;
  color: #475569;
  transition: all 0.15s ease;
  display: flex;
  align-items: center;
  gap: 8px;
}

div.stButton > button:hover {
  background-color: #F1F5F9;
  color: #0F172A;
  border-color: #CBD5E1;
}

.footer-text {
  text-align: center;
  font-size: 12.5px;
  color: #94A3B8;
  margin-top: 30px;
}
</style>
        """,
        unsafe_allow_html=True,
    )


def render_login_screen(mascot_b64: str) -> None:
    st.markdown(
        f"""
<div style="max-width:700px;margin:30px auto 20px auto;background:#FFFFFF;border:1px solid #E2E8F0;border-radius:24px;padding:32px 36px;box-shadow:0 8px 30px rgba(0,0,0,0.06);text-align:center;">
  {'<img src="data:image/jpeg;base64,' + mascot_b64 + '" style="width:95px;height:95px;border-radius:20px;object-fit:cover;box-shadow:0 4px 16px rgba(0,0,0,0.08);margin-bottom:14px;">' if mascot_b64 else ''}
  <h1 style="font-size:28px;font-weight:900;color:#0F172A;margin:0 0 6px 0;letter-spacing:-0.02em;">PortalPulse Gateway 🛡️</h1>
  <p style="font-size:14px;color:#64748B;margin:0 0 24px 0;">Autonomous Closed-Loop Traffic Control & Prescriptive Resilience</p>
  <div style="background:#F0FDF4;border:1px solid #BBF7D0;border-radius:12px;padding:10px;font-size:12.5px;color:#166534;font-weight:700;margin-bottom:20px;">
    🔐 Role-Based Cryptographic Access Tokens (HMAC-SHA256 Constant-Time Verification)
  </div>
</div>
        """,
        unsafe_allow_html=True,
    )

    col_box, _ = st.columns([1, 0.01])
    with col_box:
        login_tab1, login_tab2, login_tab3 = st.tabs(["🎓 Student Login", "👨‍🏫 Faculty Login", "🛡️ Master Admin Login"])

        with login_tab1:
            st.markdown("##### Student Portal Access")
            s_enroll = st.text_input("Enrollment Number", value="2024CS1001", placeholder="e.g. 2024CS1001").strip().upper()
            s_key = st.text_input("Student Access Token", value=ROLE_ACCESS_TOKENS["student"], type="password")

            if st.button("🚀 Enter Student Portal", type="primary", use_container_width=True):
                role = validate_role_access_token(s_key)
                if role in ["student", "admin"]:
                    st.session_state.authenticated = True
                    st.session_state.current_role = "student"
                    st.session_state.user_identifier = s_enroll
                    st.session_state.active_nav = "My Student Portal"
                    st.rerun()
                else:
                    st.error("Invalid Student Access Token. Use the demo token provided.")

        with login_tab2:
            st.markdown("##### Faculty Studio Access")
            f_id = st.text_input("Faculty ID", value="FAC-CSE-101", placeholder="e.g. FAC-CSE-101").strip()
            f_key = st.text_input("Faculty Access Token", value=ROLE_ACCESS_TOKENS["faculty"], type="password")

            if st.button("🚀 Enter Faculty Studio", type="primary", use_container_width=True):
                role = validate_role_access_token(f_key)
                if role in ["faculty", "admin"]:
                    st.session_state.authenticated = True
                    st.session_state.current_role = "faculty"
                    st.session_state.user_identifier = f_id
                    st.session_state.active_nav = "Faculty Studio"
                    st.rerun()
                else:
                    st.error("Invalid Faculty Access Token. Use the demo token provided.")

        with login_tab3:
            st.markdown("##### Master Admin Control Tower")
            a_key = st.text_input("Master Admin Token", value=ROLE_ACCESS_TOKENS["admin"], type="password")

            if st.button("👑 Enter Master Admin Tower", type="primary", use_container_width=True):
                role = validate_role_access_token(a_key)
                if role == "admin":
                    st.session_state.authenticated = True
                    st.session_state.current_role = "admin"
                    st.session_state.user_identifier = "Master Architect"
                    st.session_state.active_nav = "Control Tower"
                    st.rerun()
                else:
                    st.error("Invalid Master Admin Access Token.")


def render_sidebar(tel: dict) -> Tuple[str, str]:
    with st.sidebar:
        st.markdown(
            """
<div style="display:flex;align-items:center;gap:10px;margin-bottom:16px;">
  <div style="font-size:26px;">🛡️</div>
  <div>
    <div style="font-weight:900;font-size:19px;color:#0F172A;letter-spacing:-0.02em;">PortalPulse</div>
    <div style="font-size:11.5px;color:#64748B;">Autonomous Traffic Control</div>
  </div>
</div>
            """,
            unsafe_allow_html=True,
        )

        role = st.session_state.get("current_role", "admin")
        role_badges = {
            "admin": ("🛡️ MASTER ADMIN", "#DC2626", "#FEF2F2", "#FECACA"),
            "faculty": ("👨‍🏫 FACULTY", "#D97706", "#FFFBEB", "#FDE68A"),
            "student": ("🎓 STUDENT", "#16A34A", "#F0FDF4", "#BBF7D0"),
        }
        title, fg, bg, border = role_badges.get(role, role_badges["admin"])
        st.markdown(
            f"""
<div style="background:{bg};border:1px solid {border};border-radius:10px;padding:8px 12px;margin-bottom:14px;">
  <div style="font-size:10px;font-weight:800;color:{fg};text-transform:uppercase;">Active Account</div>
  <div style="font-size:12.5px;font-weight:800;color:#0F172A;">{st.session_state.get('user_identifier', title)}</div>
</div>
            """,
            unsafe_allow_html=True,
        )

        if role == "admin":
            nav_list = NAV_ADMIN
        elif role == "faculty":
            nav_list = NAV_FACULTY
        else:
            nav_list = NAV_STUDENT

        available_labels = [label for label, _ in nav_list]
        if st.session_state.active_nav not in available_labels:
            st.session_state.active_nav = available_labels[0]

        for label, icon in nav_list:
            is_active = st.session_state.active_nav == label
            btn_style = "primary" if is_active else "secondary"
            if st.button(f"{icon}  {label}", key=f"nav_{label}", type=btn_style, use_container_width=True):
                st.session_state.active_nav = label
                st.rerun()

        st.markdown("<hr style='border:0;border-top:1px solid #E2E8F0;margin:16px 0;'>", unsafe_allow_html=True)

        if st.button("🚪 Logout / Switch Persona", use_container_width=True):
            st.session_state.authenticated = False
            st.session_state.current_role = None
            st.session_state.user_identifier = None
            st.rerun()

        st.markdown("<hr style='border:0;border-top:1px solid #E2E8F0;margin:16px 0;'>", unsafe_allow_html=True)
        st.markdown("<div style='font-size:11px;font-weight:800;color:#64748B;text-transform:uppercase;margin-bottom:8px;'>Control Loop State</div>", unsafe_allow_html=True)

        mode = tel.get("risk_state", "SAFE")
        st.markdown(
            f"""
<div style="display:flex;align-items:center;justify-content:space-between;padding:6px 10px;background:{'#ECFDF5' if mode == 'SAFE' else '#F8FAFC'};border-radius:8px;font-size:12px;color:{'#059669' if mode == 'SAFE' else '#64748B'};font-weight:700;margin-bottom:4px;">
  <span>🟢 SAFE (Monitor)</span>
  <span>{'✓' if mode == 'SAFE' else ''}</span>
</div>
<div style="display:flex;align-items:center;justify-content:space-between;padding:6px 10px;background:{'#FFFBEB' if mode == 'WARNING' else '#F8FAFC'};border-radius:8px;font-size:12px;color:{'#D97706' if mode == 'WARNING' else '#64748B'};font-weight:700;margin-bottom:4px;">
  <span>🟡 PREPARE (Throttle/Arm)</span>
  <span>{'✓' if mode == 'WARNING' else ''}</span>
</div>
<div style="display:flex;align-items:center;justify-content:space-between;padding:6px 10px;background:{'#FEF2F2' if mode == 'CRITICAL' else '#F8FAFC'};border-radius:8px;font-size:12px;color:{'#DC2626' if mode == 'CRITICAL' else '#64748B'};font-weight:700;">
  <span>🔴 CRITICAL (Protect/Shed)</span>
  <span>{'✓' if mode == 'CRITICAL' else ''}</span>
</div>
            """,
            unsafe_allow_html=True,
        )

    return st.session_state.active_nav, st.session_state.current_role


def main() -> None:
    st.set_page_config(page_title="PortalPulse · Closed-Loop Traffic Intelligence", page_icon="🛡️", layout="wide")
    inject_custom_css()
    init_db()

    banner_b64 = get_image_base64(BANNER_PATH)
    mascot_b64 = get_image_base64(MASCOT_PATH)
    campus_b64 = get_image_base64(CAMPUS_PATH)

    if not st.session_state.get("authenticated", False):
        if banner_b64:
            st.markdown(f'<div class="banner-container"><img src="data:image/jpeg;base64,{banner_b64}"></div>', unsafe_allow_html=True)
        render_login_screen(mascot_b64)
        return

    # Initialize State
    if "selected_scenario" not in st.session_state:
        st.session_state.selected_scenario = "Result Declaration Rush"
    if "user_demand" not in st.session_state:
        st.session_state.user_demand = 8500
    if "num_pods" not in st.session_state:
        st.session_state.num_pods = 4
    if "db_pool_size" not in st.session_state:
        st.session_state.db_pool_size = 100
    if "cache_hit_pct" not in st.session_state:
        st.session_state.cache_hit_pct = 70
    if "waiting_room" not in st.session_state:
        st.session_state.waiting_room = False
    if "degraded_mode" not in st.session_state:
        st.session_state.degraded_mode = False
    if "fault_type" not in st.session_state:
        st.session_state.fault_type = "None"

    # Compute Telemetry
    tel = synthesize_telemetry(
        scenario_name=st.session_state.selected_scenario,
        users=int(st.session_state.user_demand),
        num_pods=int(st.session_state.num_pods),
        db_pool_size=int(st.session_state.db_pool_size),
        cache_hit_ratio=float(st.session_state.cache_hit_pct) / 100.0,
        waiting_room_enabled=st.session_state.waiting_room,
        degraded_mode=st.session_state.degraded_mode,
        fault_type=st.session_state.fault_type,
    )

    current_tab, current_role = render_sidebar(tel)
    db_stats = get_db_stats()

    if banner_b64:
        st.markdown(f'<div class="banner-container"><img src="data:image/jpeg;base64,{banner_b64}"></div>', unsafe_allow_html=True)

    # Top Hero Header
    st.markdown(
        f"""
<div class="header-box">
  <div class="header-title">
    <div style="font-size:12.5px;font-weight:700;color:#64748B;margin-bottom:4px;">Authenticated Account: <b>{st.session_state.get('user_identifier', 'User')}</b> ({current_role.upper()}) 👋</div>
    <h1>Closed-Loop Intelligence & Autonomous Control Tower 🌱</h1>
    <p>Predictive ML router, prescriptive capacity planning, and autonomous traffic protection loop. ✨</p>
  </div>
  <div style="display:flex;align-items:center;gap:16px;">
    <div style="background:#F0FDF4;border:1px solid #BBF7D0;border-radius:12px;padding:8px 14px;text-align:right;">
      <div style="font-size:11px;font-weight:800;color:#16A34A;text-transform:uppercase;">REPOSITORY PERSISTENCE & CACHE</div>
      <div style="font-size:12px;color:#15803D;font-weight:800;">{db_stats['student_count']:,} Students · {db_stats['cache']['backend']}</div>
    </div>
    {'<img src="data:image/jpeg;base64,' + mascot_b64 + '" style="width:75px;height:75px;border-radius:16px;object-fit:cover;box-shadow:0 4px 12px rgba(0,0,0,0.06);">' if mascot_b64 else ''}
  </div>
</div>
        """,
        unsafe_allow_html=True,
    )

    # =========================================================================
    # ROLE: STUDENT PERSONA WORKSPACE
    # =========================================================================
    if current_role == "student":
        if current_tab in ["My Student Portal", "Student Portal & DB"]:
            st.markdown('<div class="main-card"><div class="card-title">🎓 Student Academic Portal</div><div class="card-subtitle">Personal enrolled courses, grade card, and real-time database query timing.</div></div>', unsafe_allow_html=True)
            st.markdown("<br>", unsafe_allow_html=True)

            s_enroll = st.session_state.get("user_identifier", "2024CS1001")

            # ── Profile Card ──
            profile = get_profile(s_enroll, "student")
            st.markdown(
                f"""
<div style="background:#FFFFFF;border:1px solid #E2E8F0;border-radius:18px;padding:22px 24px;box-shadow:0 2px 8px rgba(0,0,0,0.02);margin-bottom:20px;">
  <div style="display:flex;justify-content:space-between;align-items:flex-start;">
    <div>
      <div style="display:flex;align-items:center;gap:10px;margin-bottom:6px;">
        <div style="background:#F0FDF4;border:1px solid #BBF7D0;border-radius:8px;padding:4px 10px;font-size:11px;font-weight:800;color:#16A34A;text-transform:uppercase;">🎓 Student Persona</div>
        <div style="background:#EFF6FF;border:1px solid #BFDBFE;border-radius:8px;padding:4px 10px;font-size:11px;font-weight:800;color:#1D4ED8;">{profile.get('status', 'ACTIVE')}</div>
      </div>
      <div style="font-size:24px;font-weight:900;color:#0F172A;margin-bottom:2px;">{profile['name']}</div>
      <div style="font-size:13px;color:#64748B;"><b>Enrollment:</b> {profile['identifier']} &nbsp;|&nbsp; <b>Email:</b> {profile['email']}</div>
    </div>
    <div style="text-align:right;">
      <div style="font-size:11px;color:#94A3B8;font-weight:700;">CURRENT CGPA</div>
      <div style="font-size:32px;font-weight:900;color:#10B981;">{profile.get('cgpa', 'N/A')}</div>
    </div>
  </div>
  <div style="display:flex;flex-wrap:wrap;gap:10px;margin-top:14px;">
    <div style="background:#F8FAFC;padding:8px 14px;border-radius:10px;font-size:12px;"><b>Department:</b> {profile['department']}</div>
    <div style="background:#F8FAFC;padding:8px 14px;border-radius:10px;font-size:12px;"><b>Year:</b> {profile.get('year', 'N/A')} (4-Year B.Tech)</div>
    <div style="background:#F8FAFC;padding:8px 14px;border-radius:10px;font-size:12px;"><b>Semester:</b> {profile.get('semester', 'N/A')}</div>
    <div style="background:#F8FAFC;padding:8px 14px;border-radius:10px;font-size:12px;"><b>Advisor:</b> {profile.get('academic_advisor', 'N/A')}</div>
    <div style="background:#F8FAFC;padding:8px 14px;border-radius:10px;font-size:12px;"><b>Attendance:</b> {profile.get('attendance_rate_pct', 'N/A')}%</div>
    <div style="background:#F8FAFC;padding:8px 14px;border-radius:10px;font-size:12px;"><b>Credits Completed:</b> {profile.get('credit_hours_completed', 'N/A')}</div>
  </div>
</div>
                """,
                unsafe_allow_html=True,
            )

            # ── Results ──
            res = get_student_results(s_enroll, bypass_cache=False)

            if res.get("found"):
                s = res["student"]
                badge_color = "#10B981" if res.get("cache_hit") else "#3B82F6"
                st.markdown(
                    f"""
<div style="background:#FFFFFF;border:1px solid #E2E8F0;border-radius:14px;padding:14px 18px;box-shadow:0 2px 6px rgba(0,0,0,0.02);margin-bottom:16px;">
  <div style="display:flex;justify-content:space-between;align-items:center;">
    <div style="font-size:15px;font-weight:800;color:#0F172A;">📄 Published Course Grades</div>
    <div style="background:{badge_color};color:#FFFFFF;padding:4px 10px;border-radius:8px;font-size:11px;font-weight:700;">{res['source']} ({res['query_duration_ms']} ms)</div>
  </div>
</div>
                    """,
                    unsafe_allow_html=True,
                )
                st.dataframe(pd.DataFrame(res["results"])[["semester", "subject_code", "subject_name", "credits", "grade", "points"]], use_container_width=True, hide_index=True)
            else:
                st.warning("Student profile not found in database.")

        elif current_tab == "Session Health & Redirect Risk":
            st.markdown('<div class="main-card"><div class="card-title">🛡️ Live Session Stability & Redirect Risk Meter</div><div class="card-subtitle">Real-time portal load monitoring to ensure your session remains active during peak rush.</div></div>', unsafe_allow_html=True)
            st.markdown("<br>", unsafe_allow_html=True)

            risk_pct = tel["redirect_risk"]
            risk_color = "#10B981" if risk_pct < 20.0 else ("#F59E0B" if risk_pct < 60.0 else "#EF4444")
            status_text = "🟢 SESSION STABLE — LOW REDIRECT RISK" if risk_pct < 20.0 else ("🟡 MODERATE CONGESTION — QUEUEING ACTIVE" if risk_pct < 60.0 else "🔴 HIGH SPIKE TRAFFIC — REDIRECT RISK ELEVATED")
            advice_text = "Traffic is well within safe capacity limits. Your session will remain fast and uninterrupted." if risk_pct < 20.0 else "Emergency protection active. Requests are rate-limited to preserve database transaction stability."

            st.markdown(
                f"""
<div class="risk-callout" style="background:{'#FEF2F2' if risk_pct >= 60 else ('#FFFBEB' if risk_pct >= 20 else '#F0FDF4')};border:2px solid {risk_color};">
  <div style="font-size:13px;font-weight:800;color:{risk_color};text-transform:uppercase;">Live Student Redirect & Timeout Risk</div>
  <div class="risk-number" style="color:{risk_color};">{risk_pct}%</div>
  <div style="font-size:16px;font-weight:800;color:#0F172A;margin-top:6px;">{status_text}</div>
  <div style="font-size:13.5px;color:#475569;margin-top:8px;max-width:550px;margin-left:auto;margin-right:auto;">{advice_text}</div>
</div>
                """,
                unsafe_allow_html=True,
            )
        return

    # =========================================================================
    # ROLE: FACULTY PERSONA WORKSPACE
    # =========================================================================
    if current_role == "faculty":
        if current_tab == "Faculty Studio":
            st.markdown('<div class="main-card"><div class="card-title">👨‍🏫 Faculty Academic Studio</div><div class="card-subtitle">Your profile, course student rosters, grade submission, and AI traffic forecast — all in one place.</div></div>', unsafe_allow_html=True)
            st.markdown("<br>", unsafe_allow_html=True)

            f_id = st.session_state.get("user_identifier", "FAC-CSE-101")

            # ── Faculty Profile Card ──
            profile = get_profile(f_id, "faculty")
            st.markdown(
                f"""
<div style="background:#FFFFFF;border:1px solid #E2E8F0;border-radius:18px;padding:22px 24px;box-shadow:0 2px 8px rgba(0,0,0,0.02);margin-bottom:20px;">
  <div style="display:flex;justify-content:space-between;align-items:flex-start;">
    <div>
      <div style="display:flex;align-items:center;gap:10px;margin-bottom:6px;">
        <div style="background:#FFFBEB;border:1px solid #FDE68A;border-radius:8px;padding:4px 10px;font-size:11px;font-weight:800;color:#D97706;text-transform:uppercase;">👨‍🏫 Faculty Member</div>
        <div style="background:#EFF6FF;border:1px solid #BFDBFE;border-radius:8px;padding:4px 10px;font-size:11px;font-weight:800;color:#1D4ED8;">{profile.get('designation', 'Professor')}</div>
      </div>
      <div style="font-size:24px;font-weight:900;color:#0F172A;margin-bottom:2px;">{profile['name']}</div>
      <div style="font-size:13px;color:#64748B;"><b>Faculty ID:</b> {profile['identifier']} &nbsp;|&nbsp; <b>Email:</b> {profile['email']}</div>
    </div>
    <div style="text-align:right;">
      <div style="font-size:11px;color:#94A3B8;font-weight:700;">STUDENTS ENROLLED</div>
      <div style="font-size:32px;font-weight:900;color:#D97706;">{profile.get('total_students_enrolled', 'N/A')}</div>
    </div>
  </div>
  <div style="display:flex;flex-wrap:wrap;gap:10px;margin-top:14px;">
    <div style="background:#F8FAFC;padding:8px 14px;border-radius:10px;font-size:12px;"><b>Department:</b> {profile['department']}</div>
    <div style="background:#F8FAFC;padding:8px 14px;border-radius:10px;font-size:12px;"><b>Courses:</b> {profile.get('courses_taught', 'N/A')}</div>
    <div style="background:#F8FAFC;padding:8px 14px;border-radius:10px;font-size:12px;"><b>Office:</b> {profile.get('office_location', 'N/A')}</div>
    <div style="background:#F8FAFC;padding:8px 14px;border-radius:10px;font-size:12px;"><b>Office Hours:</b> {profile.get('office_hours', 'N/A')}</div>
    <div style="background:#F8FAFC;padding:8px 14px;border-radius:10px;font-size:12px;"><b>Research Lab:</b> {profile.get('research_lab', 'N/A')}</div>
  </div>
</div>
                """,
                unsafe_allow_html=True,
            )

            # ── Grade Submission & Roster ──
            f_col1, f_col2 = st.columns([1.1, 1.9])
            with f_col1:
                st.subheader("📝 Grade Submission & Publishing")
                with st.form("faculty_grade_form"):
                    f_enroll = st.text_input("Student Enrollment No*", value="2024CS1001").strip().upper()
                    f_sem = st.selectbox("Semester*", options=list(range(1, 9)), index=0)
                    f_sub = st.text_input("Subject Code*", value="CS501-1")
                    f_grade = st.selectbox("Assign Grade*", options=["O (10.0)", "A+ (9.0)", "A (8.0)", "B+ (7.0)", "B (6.0)", "F (0.0)"], index=1)

                    grade_map = {"O (10.0)": ("O", 10.0), "A+ (9.0)": ("A+", 9.0), "A (8.0)": ("A", 8.0), "B+ (7.0)": ("B+", 7.0), "B (6.0)": ("B", 6.0), "F (0.0)": ("F", 0.0)}
                    publish_btn = st.form_submit_button("📤 Publish Grade Update", type="primary", use_container_width=True)
                    if publish_btn:
                        g_letter, g_pts = grade_map[f_grade]
                        ok, msg = update_student_grade(f_enroll, f_sem, f_sub, g_letter, g_pts)
                        if ok:
                            st.success(msg)
                        else:
                            st.error(msg)

            with f_col2:
                st.subheader("📋 Departmental Student Roster")
                dept_select = st.selectbox("Filter by Department", options=["Computer Science & Engineering", "Information Technology", "Electronics & Communication", "Mechanical Engineering", "Electrical Engineering"])
                dept_students = get_students_by_department(dept_select)
                if dept_students:
                    st.dataframe(pd.DataFrame(dept_students)[["enrollment_no", "name", "year", "semester", "cgpa", "status"]], use_container_width=True, hide_index=True)
                else:
                    st.info("No students found in this department.")

            # ── AI Traffic Forecast (merged into Faculty Studio) ──
            st.markdown("---")
            today_str = datetime.now().strftime("%B %d, %Y")
            with st.expander(f"📈 AI Traffic & Attendance Forecast for Today ({today_str})", expanded=False):
                fc1, fc2, fc3, fc4 = st.columns(4)
                fc1.metric("Predicted Total Queries Today", "148,500 reqs", "↑ 14% vs yesterday")
                fc2.metric("Peak Rush Window", "10:30 AM - 12:45 PM", "Result Publication")
                fc3.metric("Expected Max Concurrency", "8,900 students", "92% Safe Capacity")
                fc4.metric("Recommended Assignment Due Time", "11:59 PM (Off-Peak)", "Saves 35% DB Load")

                hours = [f"{h}:00" for h in range(8, 22)]
                forecast_traffic = [2400, 4800, 8900, 8200, 5400, 4200, 6100, 7800, 6500, 4300, 3100, 2100, 1500, 950]
                fig_fc = px.line(x=hours, y=forecast_traffic, markers=True, labels={"x": "Hour of Day", "y": "Projected Concurrent Students"})
                fig_fc.update_traces(line_color="#3B82F6", line_width=3)
                fig_fc.add_hline(y=tel["safe_capacity"], line_dash="dash", line_color="#EF4444", annotation_text=f"Safe Cap ({tel['safe_capacity']:,.0f})")
                fig_fc.update_layout(height=320, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#FFFFFF", margin=dict(l=30, r=20, t=20, b=30))
                st.plotly_chart(fig_fc, use_container_width=True)

        return

    # =========================================================================
    # ROLE: MASTER ADMIN WORKSPACE
    # =========================================================================

    # 1. TAB: CONTROL TOWER (PRODUCTION OBSERVABILITY & CLOSED-LOOP)
    if current_tab == "Control Tower":
        st.markdown('<div class="main-card"><div class="card-title">🗼 PortalPulse Control Tower & Production Observability</div><div class="card-subtitle">Real-time APM telemetry, Model Arbitration consensus with uncertainty bands, MLOps drift monitor, and autonomous closed-loop traffic control.</div></div>', unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)

        # ── Admin Profile Card ──
        profile = get_profile(st.session_state.get("user_identifier", "Master Architect"), "admin")
        st.markdown(
            f"""
<div style="background:#FFFFFF;border:1px solid #E2E8F0;border-radius:18px;padding:22px 24px;box-shadow:0 2px 8px rgba(0,0,0,0.02);margin-bottom:20px;">
  <div style="display:flex;justify-content:space-between;align-items:flex-start;">
    <div>
      <div style="display:flex;align-items:center;gap:10px;margin-bottom:6px;">
        <div style="background:#FEF2F2;border:1px solid #FECACA;border-radius:8px;padding:4px 10px;font-size:11px;font-weight:800;color:#DC2626;text-transform:uppercase;">🛡️ Master Admin</div>
        <div style="background:#EFF6FF;border:1px solid #BFDBFE;border-radius:8px;padding:4px 10px;font-size:11px;font-weight:800;color:#1D4ED8;">{profile.get('clearance_level', 'Tier-0 Superadmin')}</div>
      </div>
      <div style="font-size:24px;font-weight:900;color:#0F172A;margin-bottom:2px;">{profile['name']}</div>
      <div style="font-size:13px;color:#64748B;"><b>ID:</b> {profile['identifier']} &nbsp;|&nbsp; <b>Email:</b> {profile.get('email', 'N/A')}</div>
    </div>
    <div style="text-align:right;">
      <div style="font-size:11px;color:#94A3B8;font-weight:700;">UPTIME SLA</div>
      <div style="font-size:26px;font-weight:900;color:#DC2626;">{profile.get('uptime_sla_guarantee', '99.95%')}</div>
    </div>
  </div>
  <div style="display:flex;flex-wrap:wrap;gap:10px;margin-top:14px;">
    <div style="background:#F8FAFC;padding:8px 14px;border-radius:10px;font-size:12px;"><b>Clusters:</b> {profile.get('supervised_clusters', 'N/A')}</div>
    <div style="background:#F8FAFC;padding:8px 14px;border-radius:10px;font-size:12px;"><b>Auth:</b> {profile.get('authentication_authority', 'N/A')}</div>
    <div style="background:#F8FAFC;padding:8px 14px;border-radius:10px;font-size:12px;"><b>Policy:</b> {profile.get('active_policy', 'N/A')}</div>
  </div>
</div>
            """,
            unsafe_allow_html=True,
        )

        # ML Router inference & Drift Evaluation
        ml_res = MODEL_ROUTER.predict(
            hour=datetime.now().hour,
            day_of_week=datetime.now().weekday(),
            is_weekend=1 if datetime.now().weekday() >= 5 else 0,
            is_result_window=1 if "Result" in st.session_state.selected_scenario else 0,
            concurrent_users=int(st.session_state.user_demand),
            requests_per_sec=tel["rps"],
        )
        drift_res = DRIFT_DETECTOR.evaluate_live_drift(
            current_users=int(st.session_state.user_demand),
            current_rps=tel["rps"],
            current_cpu=tel["cpu"],
            current_latency=tel["latency"],
            current_db_pool=tel["db_pool_util"],
        )
        advice = PRESCRIPTIVE_ADVISOR.advise(
            scenario_name=st.session_state.selected_scenario,
            concurrent_users=int(st.session_state.user_demand),
            num_pods=int(st.session_state.num_pods),
            db_pool_size=int(st.session_state.db_pool_size),
            cache_hit_ratio=float(st.session_state.cache_hit_pct) / 100.0,
            waiting_room_enabled=st.session_state.waiting_room,
            degraded_mode=st.session_state.degraded_mode,
        )

        # APM Metrics Row
        k1, k2, k3, k4, k5, k6 = st.columns(6)
        k1.metric("Active Users", f"{tel['users']:,}", f"{tel['rps']:,.0f} RPS")
        k2.metric("System CPU", f"{tel['cpu']:.1f}%", f"{tel['num_pods']} Pods")
        k3.metric("P95 Latency", f"{tel['latency']:.0f} ms", f"SLA: 800 ms")
        k4.metric("Redis Hit Rate", f"{int(tel['cache_hit_ratio']*100)}%", f"{db_stats['cache']['hits']} Hits")
        k5.metric("DB Pool Utilization", f"{tel['db_pool_util']:.0f}%", f"{tel['db_conns']} / {tel['db_pool_size']}")
        k6.metric("System State", tel["risk_state"], tel["bottleneck"][:22] + "...")

        st.markdown("---")

        # Three-Column Control Deck: ML Consensus & Uncertainty | MLOps Drift | Prescriptive Advisor
        col_ml, col_drift, col_presc = st.columns([1.1, 1.0, 1.2])

        with col_ml:
            st.markdown("##### 🧠 Model Arbitration & Uncertainty")
            st.markdown(
                f"""
<div style="background:#FFFFFF;border:1px solid #E2E8F0;border-radius:14px;padding:16px;box-shadow:0 2px 6px rgba(0,0,0,0.02);">
  <div style="font-size:11px;font-weight:800;color:#64748B;text-transform:uppercase;">Consensus Predicted Safe Capacity</div>
  <div style="font-size:30px;font-weight:900;color:#0F172A;margin:4px 0;">{ml_res['consensus_capacity']:,.0f} <span style="font-size:14px;color:#64748B;">users</span></div>
  <div style="display:flex;justify-content:space-between;align-items:center;margin:8px 0 12px 0;">
    <span style="font-size:12px;color:#475569;">Confidence: <b>{ml_res['confidence_pct']}%</b></span>
    <span style="font-size:11px;background:#EFF6FF;color:#1D4ED8;padding:2px 8px;border-radius:6px;font-weight:700;">Variance: {ml_res['variance']}</span>
  </div>
  <div style="background:#F8FAFC;border:1px solid #E2E8F0;border-radius:8px;padding:8px 10px;font-size:11.5px;color:#334155;">
    • <b>90% Prediction Range:</b> {ml_res['confidence_band_90'][0]:,.0f} – {ml_res['confidence_band_90'][1]:,.0f} users<br>
    • <b>95% Prediction Range:</b> {ml_res['confidence_band_95'][0]:,.0f} – {ml_res['confidence_band_95'][1]:,.0f} users<br>
    • <b>Inference Latency:</b> {ml_res['inference_time_ms']} ms
  </div>
</div>
                """,
                unsafe_allow_html=True,
            )

        with col_drift:
            st.markdown("##### 🔬 MLOps Data Drift Monitor")
            st.markdown(
                f"""
<div style="background:#FFFFFF;border:1px solid #E2E8F0;border-radius:14px;padding:16px;box-shadow:0 2px 6px rgba(0,0,0,0.02);">
  <div style="display:flex;justify-content:space-between;align-items:center;">
    <div style="font-size:11px;font-weight:800;color:#64748B;text-transform:uppercase;">Model Health Status</div>
    <div style="font-size:11px;font-weight:800;color:{drift_res['status_color']};">{drift_res['status']}</div>
  </div>
  <div style="font-size:26px;font-weight:900;color:{drift_res['status_color']};margin:4px 0;">{drift_res['model_accuracy_pct']}% <span style="font-size:12px;color:#64748B;font-weight:600;">Est. Accuracy</span></div>
  <div style="font-size:12px;color:#475569;margin:6px 0;">
    Feature Drift: <b>{drift_res['feature_drift_pct']}%</b> (PSI: {drift_res['psi_score']})<br>
    OOD Traffic: <b>{drift_res['ood_traffic_pct']}%</b>
  </div>
  <div style="background:{'#FEF2F2' if drift_res['status'] == 'RETRAIN_RECOMMENDED' else '#F0FDF4'};border:1px solid {'#FECACA' if drift_res['status'] == 'RETRAIN_RECOMMENDED' else '#BBF7D0'};border-radius:8px;padding:8px 10px;font-size:11.5px;color:#1E293B;">
    {drift_res['action_recommendation']}
  </div>
</div>
                """,
                unsafe_allow_html=True,
            )

        with col_presc:
            st.markdown("##### 📋 Prescriptive Sizing Advisor")
            st.markdown(
                f"""
<div style="background:#FFFFFF;border:1px solid #E2E8F0;border-radius:14px;padding:16px;box-shadow:0 2px 6px rgba(0,0,0,0.02);">
  <div style="font-size:11px;font-weight:800;color:#64748B;text-transform:uppercase;">Prescriptive Action Sizing</div>
  <div style="font-size:18px;font-weight:800;color:#0F172A;margin:4px 0;">{advice['state_badge']}</div>
  <div style="font-size:12px;color:#334155;margin-bottom:8px;">
    • <b>Target App Pods:</b> {advice['target_pods']} pods (Current: {tel['num_pods']})<br>
    • <b>Target DB Pool:</b> {advice['target_db_pool']} conns (Current: {tel['db_pool_size']})<br>
    • <b>Est. Capacity after Actions:</b> <span style="color:#10B981;font-weight:800;">{advice['estimated_new_capacity']:,.0f} users (+{advice['capacity_gain_pct']}%)</span>
  </div>
</div>
                """,
                unsafe_allow_html=True,
            )

        st.markdown("---")

        # Interactive Closed-Loop Demonstration
        st.markdown("##### 🔄 Autonomous Closed-Loop Mitigation Demonstration")
        st.markdown("<p style='font-size:13px;color:#64748B;'>Observe real-time control feedback: <i>Traffic Surge → Telemetry Spike → ML Saturation Detection → Autonomous Protection (Queue + HPA Pods + Redis Pre-warm) → Telemetry Stabilization.</i></p>", unsafe_allow_html=True)

        loop_btn = st.button("▶️ Run Live Closed-Loop Protection Loop", type="primary", use_container_width=True)
        if loop_btn or "closed_loop_traj" in st.session_state:
            if loop_btn:
                with st.spinner("Executing 4-stage closed loop control simulation..."):
                    st.session_state.closed_loop_traj = CLOSED_LOOP_CONTROLLER.run_closed_loop_simulation(
                        scenario_name=st.session_state.selected_scenario,
                        surge_users=int(st.session_state.user_demand),
                        initial_pods=int(st.session_state.num_pods),
                        initial_db_pool=int(st.session_state.db_pool_size),
                        initial_cache_hit=float(st.session_state.cache_hit_pct) / 100.0,
                    )

            traj = st.session_state.closed_loop_traj
            traj_df = pd.DataFrame(traj)

            c_table, c_plot = st.columns([1.3, 1.7])
            with c_table:
                st.markdown("###### 📊 Trajectory Step Log")
                for step in traj:
                    st.markdown(
                        f"""
<div style="background:#FFFFFF;border:1px solid #E2E8F0;border-left:4px solid {'#EF4444' if step['state'] == 'CRITICAL' else ('#F59E0B' if step['state'] == 'PREPARE' else '#10B981')};border-radius:10px;padding:10px 14px;margin-bottom:8px;font-size:12px;">
  <b>{step['phase']}</b> &nbsp;|&nbsp; CPU: <b>{step['cpu']}%</b> &nbsp;|&nbsp; Latency: <b>{step['latency']} ms</b> &nbsp;|&nbsp; Pods: <b>{step['pods']}</b><br>
  <span style="color:#64748B;">{step['narrative']}</span>
</div>
                        """,
                        unsafe_allow_html=True,
                    )

            with c_plot:
                st.markdown("###### 📈 Telemetry Stabilization Curves")
                fig_loop = go.Figure()
                fig_loop.add_trace(go.Scatter(x=traj_df["phase"], y=traj_df["latency"], mode="lines+markers", name="Latency (ms)", line=dict(color="#F59E0B", width=3), marker=dict(size=8)))
                fig_loop.add_trace(go.Scatter(x=traj_df["phase"], y=traj_df["cpu"], mode="lines+markers", name="CPU (%)", line=dict(color="#10B981", width=3), marker=dict(size=8)))
                fig_loop.add_hline(y=SLA_LATENCY, line_dash="dash", line_color="#EF4444", annotation_text="SLA 800ms")
                fig_loop.update_layout(height=260, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#FFFFFF", margin=dict(l=30, r=20, t=20, b=20))
                st.plotly_chart(fig_loop, use_container_width=True)

    # 2. TAB: DASHBOARD & SIMULATOR
    elif current_tab in ["Dashboard", "Simulator"]:
        st.markdown('<div style="font-size:14px;font-weight:800;color:#334155;margin-bottom:8px;">⚙️ Operational Scenario & Concurrency Presets</div>', unsafe_allow_html=True)
        c_scen, c_users = st.columns([1.2, 2.0])
        with c_scen:
            st.session_state.selected_scenario = st.selectbox(
                "Select Scenario",
                options=list(SCENARIOS.keys()),
                index=list(SCENARIOS.keys()).index(st.session_state.selected_scenario),
            )
        with c_users:
            st.session_state.user_demand = st.slider(
                "Concurrent Users (Demand)",
                min_value=500,
                max_value=25000,
                value=int(st.session_state.user_demand),
                step=100,
            )

        with st.expander("🛠️ Advanced Cluster & Mitigation Controls (Pods, DB Pool, Redis Caching, Waiting Room)", expanded=(current_tab == "Simulator")):
            i1, i2, i3, i4, i5, i6 = st.columns(6)
            with i1:
                st.session_state.num_pods = st.number_input("Backend App Pods", min_value=1, max_value=32, value=int(st.session_state.num_pods), step=1)
            with i2:
                st.session_state.db_pool_size = st.number_input("DB Connection Pool", min_value=20, max_value=500, value=int(st.session_state.db_pool_size), step=10)
            with i3:
                st.session_state.cache_hit_pct = st.slider("Redis Cache Hit %", min_value=0, max_value=100, value=int(st.session_state.cache_hit_pct), step=5)
            with i4:
                st.session_state.waiting_room = st.checkbox("Virtual Waiting Room 🚪", value=bool(st.session_state.waiting_room))
            with i5:
                st.session_state.degraded_mode = st.checkbox("Degraded Query Mode ⚡", value=bool(st.session_state.degraded_mode))
            with i6:
                st.session_state.fault_type = st.selectbox("Chaos Fault Injection", options=["None", "DB Lock Contention", "Network Degradation", "Memory Leak"])

        tel = synthesize_telemetry(
            scenario_name=st.session_state.selected_scenario,
            users=int(st.session_state.user_demand),
            num_pods=int(st.session_state.num_pods),
            db_pool_size=int(st.session_state.db_pool_size),
            cache_hit_ratio=float(st.session_state.cache_hit_pct) / 100.0,
            waiting_room_enabled=st.session_state.waiting_room,
            degraded_mode=st.session_state.degraded_mode,
            fault_type=st.session_state.fault_type,
        )

        st.markdown(
            f"""
<div class="kpi-container">
  <div class="kpi-card" style="border-left:4px solid #3B82F6;">
    <div class="kpi-header"><span>👥</span> Incoming Users</div>
    <div class="kpi-value">{tel['users']:,} <span style="font-size:12px;color:#64748B;font-weight:600;">users</span></div>
    <div class="kpi-sub" style="color:#10B981;">Admitted: {tel['admitted_users']:,} ({tel['rps']:,.0f} RPS)</div>
  </div>
  <div class="kpi-card" style="border-left:4px solid #10B981;">
    <div class="kpi-header"><span>🛡️</span> Safe Capacity (Predicted)</div>
    <div class="kpi-value">{tel['safe_capacity']:,.0f} <span style="font-size:12px;color:#64748B;font-weight:600;">users</span></div>
    <div class="kpi-sub">Pods: {tel['num_pods']} · Cache: {int(tel['cache_hit_ratio']*100)}%</div>
  </div>
  <div class="kpi-card" style="border-left:4px solid #F59E0B;">
    <div class="kpi-header"><span>🌙</span> Utilization</div>
    <div class="kpi-value">{tel['utilization']:.1f}%</div>
    <div class="kpi-sub" style="color:{'#EF4444' if tel['headroom'] <= 0 else '#10B981'};">{'Deficit: ' + str(abs(tel['headroom'])) if tel['headroom'] <= 0 else 'Headroom: ' + str(tel['headroom'])} users</div>
  </div>
  <div class="kpi-card" style="border-left:4px solid #8B5CF6;">
    <div class="kpi-header"><span>⚡</span> Latency (P95)</div>
    <div class="kpi-value">{tel['latency']:.0f} <span style="font-size:12px;color:#64748B;font-weight:600;">ms</span></div>
    <div class="kpi-sub">SLA: 800 ms ({'Breached ✗' if tel['latency'] >= SLA_LATENCY else 'Normal ✓'})</div>
  </div>
  <div class="kpi-card" style="border-left:4px solid #06B6D4;">
    <div class="kpi-header"><span>🖥️</span> CPU Utilization</div>
    <div class="kpi-value">{tel['cpu']:.1f}%</div>
    <div class="kpi-sub">DB Conns: {tel['db_conns']}/{tel['db_pool_size']} ({tel['db_pool_util']}%)</div>
  </div>
  <div class="kpi-card" style="border-left:4px solid {tel['risk_color']};background:{'#FEF2F2' if tel['risk_state'] == 'CRITICAL' else '#FFFFFF'};">
    <div class="kpi-header"><span style="color:{tel['risk_color']};">🚨</span> Risk State</div>
    <div class="kpi-value" style="color:{tel['risk_color']};font-size:18px;padding-top:4px;">{tel['risk_state']}</div>
    <div class="kpi-sub" style="color:{tel['risk_color']};font-weight:700;">{'Action Required' if tel['risk_state'] == 'CRITICAL' else 'Operating Normal'}</div>
  </div>
</div>
            """,
            unsafe_allow_html=True,
        )

        col_sim, col_chart = st.columns([1.05, 1.95])
        with col_sim:
            st.markdown(
                f"""
<div class="main-card">
  <div class="card-title">🌱 Traffic Simulator & Diagnostics</div>
  <div class="card-subtitle">Realistic scenarios. Physically consistent telemetry.</div>
  <div style="margin-bottom:10px;">
    <div style="font-size:12px;font-weight:800;color:#64748B;text-transform:uppercase;">Active Scenario: {st.session_state.selected_scenario}</div>
    <div style="font-size:12px;color:#D97706;font-weight:700;margin-top:2px;">• {SCENARIOS[st.session_state.selected_scenario]['badge']}</div>
  </div>
  <div style="display:flex;justify-content:center;margin:8px 0;">
    {'<img src="data:image/jpeg;base64,' + campus_b64 + '" style="width:100%;max-width:230px;border-radius:14px;box-shadow:0 2px 8px rgba(0,0,0,0.04);">' if campus_b64 else ''}
  </div>
  <div style="background:#F8FAFC;border:1px solid #E2E8F0;border-radius:10px;padding:8px 10px;font-size:11.5px;color:#475569;margin-top:8px;">
    ℹ️ Multi-tier breakdown: CDN ({tel['cdn_latency']}ms) + Pod CPU ({tel['app_latency']}ms) + DB Query ({tel['db_latency']}ms) + Network ({tel['net_latency']}ms).
  </div>
</div>
                """,
                unsafe_allow_html=True,
            )

        with col_chart:
            user_range = np.linspace(500, 20000, 40)
            lats = [synthesize_telemetry(st.session_state.selected_scenario, int(u), int(st.session_state.num_pods), int(st.session_state.db_pool_size), float(st.session_state.cache_hit_pct)/100.0, st.session_state.waiting_room, st.session_state.degraded_mode, st.session_state.fault_type)["latency"] for u in user_range]
            cpus = [synthesize_telemetry(st.session_state.selected_scenario, int(u), int(st.session_state.num_pods), int(st.session_state.db_pool_size), float(st.session_state.cache_hit_pct)/100.0, st.session_state.waiting_room, st.session_state.degraded_mode, st.session_state.fault_type)["cpu"] for u in user_range]

            fig = go.Figure()
            fig.add_trace(go.Scatter(x=user_range, y=lats, mode="lines+markers", name="Latency (ms)", line=dict(color="#F59E0B", width=2.6), marker=dict(size=4)))
            fig.add_trace(go.Scatter(x=user_range, y=cpus, mode="lines", name="CPU (%)", line=dict(color="#10B981", width=2.0)))
            fig.add_hline(y=SLA_LATENCY, line_dash="dash", line_color="#EF4444", annotation_text="SLA 800ms", annotation_position="top right")
            fig.add_vline(x=tel["safe_capacity"], line_dash="dot", line_color="#10B981", annotation_text=f"Safe Cap ({tel['safe_capacity']:,.0f})", annotation_position="top left")
            fig.add_trace(go.Scatter(x=[tel["users"]], y=[tel["latency"]], mode="markers", marker=dict(size=12, color="#0F172A", symbol="circle"), name="Operating Point"))

            fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#FFFFFF", font=dict(family="Plus Jakarta Sans, sans-serif", size=11, color="#64748B"), height=350, margin=dict(l=40, r=20, t=30, b=30), yaxis_type="log", legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0))
            st.plotly_chart(fig, use_container_width=True)

    # 3. TAB: CUSTOM STRESS LAB & AUTOMATED EXPERIMENT MODE
    elif current_tab == "Custom Stress Lab":
        st.markdown('<div class="main-card"><div class="card-title">🧪 Custom Stress Lab & Automated Experiment Suite</div><div class="card-subtitle">Perform manual parameter studio adjustments or launch automated multi-point sweeps to detect the saturation knee point.</div></div>', unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)

        mode_tab1, mode_tab2 = st.tabs(["🚀 Automated Experiment Mode (Knee-Point Sweep)", "🎛️ Manual Parameter Studio"])

        with mode_tab1:
            st.markdown("##### Automated Concurrency Experiment Suite")
            e_col1, e_col2, e_col3 = st.columns(3)
            with e_col1:
                exp_scen = st.selectbox("Experiment Scenario", options=list(SCENARIOS.keys()), key="exp_scen")
                exp_max_users = st.slider("Max Concurrency Sweep", min_value=5000, max_value=40000, value=30000, step=2500)
            with e_col2:
                exp_pods = st.number_input("App Pods", min_value=1, max_value=32, value=4, key="exp_pods")
                exp_db_pool = st.number_input("DB Pool Size", min_value=20, max_value=500, value=100, key="exp_db")
            with e_col3:
                exp_cache = st.slider("Redis Hit %", min_value=0, max_value=100, value=75, key="exp_cache")
                exp_fault = st.selectbox("Chaos Fault", options=["None", "DB Lock Contention", "Network Degradation", "Memory Leak"], key="exp_fault")

            if st.button("🚀 Run Automated Experiment Sweep (100 → 30,000 Users)", type="primary", use_container_width=True):
                with st.spinner("Executing multi-tier parameter sweep across concurrency range..."):
                    knee_res = find_saturation_knee(
                        scenario_name=exp_scen,
                        num_pods=int(exp_pods),
                        db_pool_size=int(exp_db_pool),
                        cache_hit_ratio=float(exp_cache) / 100.0,
                        fault_type=exp_fault,
                        max_users=int(exp_max_users),
                        num_points=25,
                    )
                    st.session_state.last_knee_res = knee_res

            if "last_knee_res" in st.session_state and st.session_state.last_knee_res:
                k_data = st.session_state.last_knee_res
                sweep_df = pd.DataFrame(k_data["sweep_data"])

                st.markdown(
                    f"""
<div style="background:#F0FDF4;border:1px solid #BBF7D0;border-radius:14px;padding:16px;margin:16px 0;display:flex;justify-content:space-between;align-items:center;">
  <div>
    <div style="font-size:12px;font-weight:800;color:#16A34A;text-transform:uppercase;">Estimated Saturation Knee Point</div>
    <div style="font-size:26px;font-weight:900;color:#15803D;">{k_data['saturation_threshold_users']:,} Concurrent Users</div>
  </div>
  <div style="text-align:right;">
    <div style="font-size:12px;color:#64748B;">Knee Point Latency</div>
    <div style="font-size:22px;font-weight:800;color:#0F172A;">{k_data['knee_latency_ms']} ms (SLA: 800ms)</div>
  </div>
</div>
                    """,
                    unsafe_allow_html=True,
                )

                fig_exp = go.Figure()
                fig_exp.add_trace(go.Scatter(x=sweep_df["users"], y=sweep_df["latency"], mode="lines+markers", name="Latency (ms)", line=dict(color="#F59E0B", width=3)))
                fig_exp.add_hline(y=SLA_LATENCY, line_dash="dash", line_color="#EF4444", annotation_text="SLA 800ms")
                fig_exp.add_vline(x=k_data["saturation_threshold_users"], line_dash="dot", line_color="#10B981", annotation_text=f"Knee: {k_data['saturation_threshold_users']:,} users")
                fig_exp.update_layout(height=360, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#FFFFFF", xaxis_title="Concurrent Virtual Users", yaxis_title="Latency (ms)")
                st.plotly_chart(fig_exp, use_container_width=True)

        with mode_tab2:
            st.markdown("##### Manual Parameter Studio")
            lab_c1, lab_c2, lab_c3 = st.columns(3)
            with lab_c1:
                custom_users = st.number_input("Demand (Users)", min_value=100, max_value=60000, value=12500, step=500)
                custom_pods = st.number_input("App Pods", min_value=1, max_value=64, value=6, step=1)
            with lab_c2:
                custom_db_pool = st.number_input("DB Pool (Conns)", min_value=10, max_value=1000, value=150, step=10)
                custom_cache = st.number_input("Cache Hit %", min_value=0, max_value=100, value=80, step=5)
            with lab_c3:
                custom_sla_lat = st.number_input("SLA Latency (ms)", min_value=100.0, max_value=5000.0, value=800.0, step=50.0)
                custom_sla_cpu = st.number_input("SLA CPU (%)", min_value=30.0, max_value=99.0, value=85.0, step=5.0)

            c_tel = synthesize_telemetry(
                scenario_name="Result Declaration Rush",
                users=int(custom_users),
                num_pods=int(custom_pods),
                db_pool_size=int(custom_db_pool),
                cache_hit_ratio=float(custom_cache) / 100.0,
                sla_latency=float(custom_sla_lat),
                sla_cpu=float(custom_sla_cpu),
            )
            st.write(f"Safe Capacity: **{c_tel['safe_capacity']:,.0f} users** | Latency: **{c_tel['latency']} ms** | CPU: **{c_tel['cpu']}%** | Risk: **{c_tel['risk_state']}**")

    # 4. TAB: ALL ACCOUNTS DIRECTORY
    elif current_tab == "All Accounts Directory":
        st.markdown('<div class="main-card"><div class="card-title">👥 All Accounts Management Directory</div><div class="card-subtitle">Master oversight of Students, Faculty, and Admin accounts stored on disk.</div></div>', unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)

        acc_tab1, acc_tab2, acc_tab3 = st.tabs(["🎓 Students Directory", "👨‍🏫 Faculty Directory", "🛡️ Master Admin Credentials"])

        with acc_tab1:
            st.markdown("##### Registered Students Directory")
            search_box = st.text_input("Search student by name, enrollment or course", placeholder="Type name or enrollment...")
            students_list = get_all_students(limit=100, search_query=search_box)
            if students_list:
                df_students = pd.DataFrame(students_list)[["enrollment_no", "name", "email", "department", "year", "semester", "cgpa", "status"]]
                st.dataframe(df_students, use_container_width=True, hide_index=True)
            else:
                st.info("No student records found.")

            if st.button("🌱 Bulk Seed 100 Sample Students"):
                with st.spinner("Seeding database..."):
                    seeded = seed_sample_students(count=100)
                    st.success(f"Seeded {seeded} students successfully!")
                    st.rerun()

        with acc_tab2:
            st.markdown("##### Faculty Directory")
            faculty_list = get_all_faculty()
            if faculty_list:
                df_fac = pd.DataFrame(faculty_list)[["faculty_id", "name", "email", "department", "designation", "courses_taught"]]
                st.dataframe(df_fac, use_container_width=True, hide_index=True)
            else:
                st.info("No faculty records found.")

        with acc_tab3:
            st.markdown("##### 🔐 Role-Based Cryptographic Access Tokens (RBAC-PAT)")
            q_df = pd.DataFrame([
                {"Role": "Master Admin (You)", "Access Token": ROLE_ACCESS_TOKENS["admin"], "Security": "HMAC-SHA256 Constant-Time", "Permissions": "Unrestricted Full Access"},
                {"Role": "Faculty Member", "Access Token": ROLE_ACCESS_TOKENS["faculty"], "Security": "HMAC-SHA256 Constant-Time", "Permissions": "Departmental Student Rosters & Grade Publishing"},
                {"Role": "Student Persona", "Access Token": ROLE_ACCESS_TOKENS["student"], "Security": "HMAC-SHA256 Constant-Time", "Permissions": "Personal Transcript & Session Health"},
            ])
            st.dataframe(q_df, use_container_width=True, hide_index=True)

    # 5. TAB: STUDENT PORTAL & DB (Admin View)
    elif current_tab == "Student Portal & DB":
        st.markdown('<div class="main-card"><div class="card-title">🎓 Student Portal & Real Database Terminal</div><div class="card-subtitle">Query real student records, semester grade cards, and measure cold SQLite vs Redis caching latency.</div></div>', unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)

        col_left, col_right = st.columns([1.2, 1.8])
        with col_left:
            st.subheader("🔍 Student Result Lookup")
            lookup_enrollment = st.text_input("Enter Student Enrollment No", value="2024CS1001").strip().upper()
            bypass = st.checkbox("Bypass Redis Cache (Force Cold Database Read)", value=False)

            if st.button("🚀 Query Student Results", type="primary", use_container_width=True):
                res = get_student_results(lookup_enrollment, bypass_cache=bypass)
                st.session_state.last_result = res

            if "last_result" in st.session_state and st.session_state.last_result:
                res = st.session_state.last_result
                if res.get("found"):
                    s = res["student"]
                    badge_color = "#10B981" if res.get("cache_hit") else "#3B82F6"
                    st.markdown(
                        f"""
<div style="background:#F8FAFC;border:1px solid #E2E8F0;border-radius:14px;padding:14px;margin-top:14px;">
  <div style="display:flex;justify-content:space-between;align-items:center;">
    <div style="font-size:16px;font-weight:800;color:#0F172A;">{s['name']}</div>
    <div style="background:{badge_color};color:#FFFFFF;padding:2px 8px;border-radius:6px;font-size:11px;font-weight:700;">{res['source']}</div>
  </div>
  <div style="font-size:12px;color:#64748B;margin:6px 0;">
    <b>Enrollment:</b> {s['enrollment_no']} &nbsp;|&nbsp; <b>Course:</b> {s['department']}<br>
    <b>Year:</b> {s['year']} &nbsp;|&nbsp; <b>Semester:</b> {s['semester']} &nbsp;|&nbsp; <b>CGPA:</b> <span style="color:#10B981;font-weight:800;">{s['cgpa']}</span>
  </div>
  <div style="font-size:11.5px;font-weight:700;color:#475569;background:#ECFDF5;padding:6px 10px;border-radius:8px;margin-top:8px;">
    ⚡ Real Query Execution Latency: <b>{res['query_duration_ms']} ms</b>
  </div>
</div>
                        """,
                        unsafe_allow_html=True,
                    )
                    st.markdown("##### 📄 Published Semester Course Grades")
                    st.dataframe(pd.DataFrame(res["results"])[["semester", "subject_code", "subject_name", "credits", "grade", "points"]], use_container_width=True, hide_index=True)
                else:
                    st.warning(res.get("message", "Record not found."))

            st.markdown("---")
            st.subheader("⚡ Database vs Redis Benchmark")
            if st.button("Run Live 60-Query Latency Benchmark", use_container_width=True):
                with st.spinner("Benchmarking SQLite joins vs Redis cache..."):
                    bench = run_db_stress_benchmark(num_queries=60)
                    if "error" not in bench:
                        st.success(f"Benchmark Complete! Redis is **{bench['speedup_factor']}x faster** than cold SQLite disk reads.")
                        b_col1, b_col2 = st.columns(2)
                        b_col1.metric("Cold DB Avg Latency", f"{bench['cold_avg_ms']} ms", f"P95: {bench['cold_p95_ms']} ms")
                        b_col2.metric("Redis Cache Avg Latency", f"{bench['cached_avg_ms']} ms", f"P95: {bench['cached_p95_ms']} ms")

        with col_right:
            st.subheader("📝 Register New Student")
            with st.form("new_student_form", clear_on_submit=True):
                n_col1, n_col2 = st.columns(2)
                with n_col1:
                    new_enrollment = st.text_input("Enrollment Number*", placeholder="e.g. 2024CS1099")
                    new_name = st.text_input("Full Name*", placeholder="e.g. Ananya Roy")
                    new_email = st.text_input("Email Address*", placeholder="ananya.roy@iem.edu.in")
                with n_col2:
                    new_dept = st.selectbox("Department*", options=["Computer Science & Engineering", "Information Technology", "Electronics & Communication", "Mechanical Engineering", "Electrical Engineering"])
                    new_year = st.selectbox("Year*", options=[1, 2, 3, 4], index=1)
                    new_sem = st.selectbox("Semester*", options=list(range(1, 9)), index=3)
                    new_cgpa = st.number_input("CGPA*", min_value=0.0, max_value=10.0, value=8.5, step=0.1)

                submit_student = st.form_submit_button("➕ Save Student to Database", type="primary", use_container_width=True)
                if submit_student:
                    if not new_enrollment or not new_name or not new_email:
                        st.error("Please fill in all required fields.")
                    else:
                        ok, msg = add_student(new_enrollment, new_name, new_email, new_dept, new_year, new_sem, new_cgpa)
                        if ok:
                            st.success(msg)
                        else:
                            st.error(msg)

    # 6. TAB: FACULTY STUDIO (Admin View)
    elif current_tab == "Faculty Studio":
        st.markdown('<div class="main-card"><div class="card-title">👨‍🏫 Faculty Academic Studio</div><div class="card-subtitle">Manage departmental course rosters, enter/update semester grades, and view grade distributions.</div></div>', unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)

        dept_select = st.selectbox("Select Department Roster", options=["Computer Science & Engineering", "Information Technology", "Electronics & Communication", "Mechanical Engineering", "Electrical Engineering"])
        dept_students = get_students_by_department(dept_select)
        if dept_students:
            st.dataframe(pd.DataFrame(dept_students)[["enrollment_no", "name", "year", "semester", "cgpa", "status"]], use_container_width=True, hide_index=True)

    # 7. TAB: TELEMETRY
    elif current_tab == "Telemetry":
        st.markdown('<div class="main-card"><div class="card-title">📊 Real-Time Server Telemetry & Queuing Analysis</div><div class="card-subtitle">Detailed breakdown of CPU, RAM, Network, DB Connection Pool and Latency Saturation</div></div>', unsafe_allow_html=True)
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Requests / Sec", f"{tel['rps']:,.0f}", f"Admitted: {tel['admitted_rps']:,.0f}")
        m2.metric("CPU Utilization", f"{tel['cpu']:.1f}%", f"Active Pods: {tel['num_pods']}")
        m3.metric("DB Connections", f"{tel['db_conns']} / {tel['db_pool_size']}", f"Util: {tel['db_pool_util']}%")
        m4.metric("Memory Usage", f"{tel['mem']:.1f}%", f"Cache: {int(tel['cache_hit_ratio']*100)}%")

        st.markdown("##### ⏱️ Multi-Tier Latency Breakdown")
        tier_df = pd.DataFrame([
            {"Tier": "Edge CDN Latency", "Latency (ms)": tel["cdn_latency"]},
            {"Tier": "Backend Pod CPU Processing", "Latency (ms)": tel["app_latency"]},
            {"Tier": "Database Query & Lock Wait", "Latency (ms)": tel["db_latency"]},
            {"Tier": "Network Egress Transport", "Latency (ms)": tel["net_latency"]},
        ])
        fig_bar = px.bar(tier_df, x="Tier", y="Latency (ms)", color="Tier", text_auto=True, height=300)
        fig_bar.update_layout(showlegend=False, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#FFFFFF")
        st.plotly_chart(fig_bar, use_container_width=True)

    # 8. TAB: DEEP LEARNING MODELS (Admin Exclusive)
    elif current_tab == "Models (ML)":
        st.markdown('<div class="main-card"><div class="card-title">⚙️ Deep Learning Architecture (PyTorch Multi-Output MLP)</div><div class="card-subtitle">Exclusive Master Admin view of Neural Network architecture, initialization strategy, and training configuration.</div></div>', unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)

        ml_c1, ml_c2 = st.columns(2)
        with ml_c1:
            st.markdown(
                """
<div style="background:#FFFFFF;border:1px solid #E2E8F0;border-radius:16px;padding:20px;box-shadow:0 2px 6px rgba(0,0,0,0.02);margin-bottom:14px;">
  <div style="font-size:14px;font-weight:800;color:#0F172A;margin-bottom:12px;">🧠 Network Architecture</div>
  <div style="display:flex;flex-direction:column;gap:8px;">
    <div style="display:flex;justify-content:space-between;padding:8px 12px;background:#F8FAFC;border-radius:10px;font-size:12.5px;">
      <span style="color:#64748B;font-weight:700;">Input Features</span>
      <span style="color:#0F172A;font-weight:800;">6 features</span>
    </div>
    <div style="display:flex;justify-content:space-between;padding:8px 12px;background:#F8FAFC;border-radius:10px;font-size:12.5px;">
      <span style="color:#64748B;font-weight:700;">Hidden Layers</span>
      <span style="color:#0F172A;font-weight:800;">128 → 64 → 32</span>
    </div>
    <div style="display:flex;justify-content:space-between;padding:8px 12px;background:#F8FAFC;border-radius:10px;font-size:12.5px;">
      <span style="color:#64748B;font-weight:700;">Output Targets</span>
      <span style="color:#0F172A;font-weight:800;">3 (CPU, Latency, Capacity)</span>
    </div>
    <div style="display:flex;justify-content:space-between;padding:8px 12px;background:#F8FAFC;border-radius:10px;font-size:12.5px;">
      <span style="color:#64748B;font-weight:700;">Optimizer</span>
      <span style="color:#0F172A;font-weight:800;">AdamW (lr=0.001)</span>
    </div>
    <div style="display:flex;justify-content:space-between;padding:8px 12px;background:#F8FAFC;border-radius:10px;font-size:12.5px;">
      <span style="color:#64748B;font-weight:700;">Loss Function</span>
      <span style="color:#0F172A;font-weight:800;">Multi-Task MSE (Dynamic Weighting)</span>
    </div>
  </div>
</div>
                """,
                unsafe_allow_html=True,
            )

        with ml_c2:
            st.markdown(
                """
<div style="background:#FFFFFF;border:1px solid #E2E8F0;border-radius:16px;padding:20px;box-shadow:0 2px 6px rgba(0,0,0,0.02);margin-bottom:14px;">
  <div style="font-size:14px;font-weight:800;color:#0F172A;margin-bottom:12px;">🔧 Regularization & Initialization</div>
  <div style="display:flex;flex-direction:column;gap:8px;">
    <div style="display:flex;align-items:center;gap:8px;padding:8px 12px;background:#F0FDF4;border:1px solid #BBF7D0;border-radius:10px;font-size:12.5px;">
      <span style="color:#16A34A;font-weight:800;">✓</span>
      <span style="color:#334155;font-weight:600;">He Normal Init (Ratio 0.88 In/Out)</span>
    </div>
    <div style="display:flex;align-items:center;gap:8px;padding:8px 12px;background:#F0FDF4;border:1px solid #BBF7D0;border-radius:10px;font-size:12.5px;">
      <span style="color:#16A34A;font-weight:800;">✓</span>
      <span style="color:#334155;font-weight:600;">BatchNorm1d (eps=1e-5)</span>
    </div>
    <div style="display:flex;align-items:center;gap:8px;padding:8px 12px;background:#F0FDF4;border:1px solid #BBF7D0;border-radius:10px;font-size:12.5px;">
      <span style="color:#16A34A;font-weight:800;">✓</span>
      <span style="color:#334155;font-weight:600;">Dropout (p=0.15)</span>
    </div>
    <div style="display:flex;align-items:center;gap:8px;padding:8px 12px;background:#F0FDF4;border:1px solid #BBF7D0;border-radius:10px;font-size:12.5px;">
      <span style="color:#16A34A;font-weight:800;">✓</span>
      <span style="color:#334155;font-weight:600;">L2 Weight Decay (λ=1e-4)</span>
    </div>
    <div style="display:flex;align-items:center;gap:8px;padding:8px 12px;background:#F0FDF4;border:1px solid #BBF7D0;border-radius:10px;font-size:12.5px;">
      <span style="color:#16A34A;font-weight:800;">✓</span>
      <span style="color:#334155;font-weight:600;">Beta (0.9, 0.999)</span>
    </div>
  </div>
</div>
                """,
                unsafe_allow_html=True,
            )

    # 9. TAB: BENCHMARKS (Admin Exclusive)
    elif current_tab == "Benchmarks (ML)":
        st.markdown('<div class="main-card"><div class="card-title">🏆 5-Model Architecture Selection Benchmark Suite</div><div class="card-subtitle">Empirical evaluation on held-out test split (28,720 train / 6,559 test records)</div></div>', unsafe_allow_html=True)
        comp_df = pd.DataFrame([
            {"Model": "XGBoost", "Family": "Gradient Boosted Trees", "Test MAE": 131.3, "Test R²": 0.913, "Inference (ms)": 0.012, "Role": "Selected Tabular Champion"},
            {"Model": "LightGBM / HistGB", "Family": "Histogram GBDT", "Test MAE": 134.1, "Test R²": 0.910, "Inference (ms)": 0.008, "Role": "Fast Edge Microservice Candidate"},
            {"Model": "PyTorch Multi-Output MLP", "Family": "Deep Neural Net (BatchNorm+He+Dropout)", "Test MAE": 139.6, "Test R²": 0.901, "Inference (ms)": 0.015, "Role": "Syllabus Deep Multi-Target Model"},
            {"Model": "Random Forest", "Family": "Bagged Ensemble", "Test MAE": 142.5, "Test R²": 0.894, "Inference (ms)": 0.045, "Role": "Robust Ensemble Variance Check"},
            {"Model": "Linear / Ridge", "Family": "Regularized Linear", "Test MAE": 284.7, "Test R²": 0.556, "Inference (ms)": 0.002, "Role": "Linear Baseline Reference"},
        ])
        st.dataframe(comp_df, use_container_width=True, hide_index=True)

    # 10. TAB: ARCHITECTURAL INSIGHTS
    elif current_tab == "Insights":
        st.markdown(
            """
<div class="main-card">
  <div class="card-title">📈 Architectural Positioning: PortalPulse vs Edge CDNs</div>
  <div style="font-size:13.5px;color:#334155;line-height:1.65;margin-top:10px;">
    <div>• <b>Edge CDN (e.g. Cloudflare):</b> Mitigates L3/L4 DDoS attacks and caches static assets, but cannot observe relational table lock queues, database connection pools, or multi-tenant database saturation.</div>
    <div style="margin-top:10px;">• <b>PortalPulse Application Layer:</b> Collects server telemetry (CPU, RAM, M/M/1 latency knee), runs real-time ML arbitration, forecasts database pool starvation minutes in advance, and enforces token-bucket admission and priority queues before the backend database crashes.</div>
  </div>
</div>
            """,
            unsafe_allow_html=True,
        )

    # 11. TAB: ARCHITECTURE & MIGRATION
    elif current_tab == "Architecture & Migration":
        render_architecture_tab()

    # 12. TAB: REPORTS
    elif current_tab == "Reports":
        st.markdown('<div class="main-card"><div class="card-title">📄 Query Audit Reports & Activity Log</div><div class="card-subtitle">Real database query audit trail with latency analytics and cache performance metrics.</div></div>', unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)

        logs = get_query_logs(limit=50)
        if logs:
            logs_df = pd.DataFrame(logs)

            # Summary metrics
            total_queries = len(logs_df)
            avg_latency = round(logs_df["duration_ms"].mean(), 3) if "duration_ms" in logs_df.columns else 0.0
            cache_hits = logs_df["cache_hit"].sum() if "cache_hit" in logs_df.columns else 0
            cache_rate = round((cache_hits / max(total_queries, 1)) * 100, 1)

            r1, r2, r3, r4 = st.columns(4)
            r1.metric("Total Logged Queries", f"{total_queries}")
            r2.metric("Avg Query Latency", f"{avg_latency} ms")
            r3.metric("Cache Hit Rate", f"{cache_rate}%", f"{cache_hits} / {total_queries} hits")
            r4.metric("Query Types", f"{logs_df['query_type'].nunique() if 'query_type' in logs_df.columns else 'N/A'}")

            st.markdown("---")
            st.markdown("##### 📜 Recent Query Audit Logs")
            st.dataframe(logs_df, use_container_width=True, hide_index=True)
        else:
            st.info("No query audit logs recorded yet. Query a student record to generate logs.")

    st.markdown(
        """
<div class="footer-text">
  🌱 <b>PortalPulse</b> learns, adapts, and protects your portal in real-time. &nbsp;|&nbsp; Made with ❤️ by PortalPulse Team
</div>
        """,
        unsafe_allow_html=True,
    )


def render_architecture_tab() -> None:
    st.markdown('<div class="main-card"><div class="card-title">⚡ Persistence Architecture & Enterprise Database Migration</div><div class="card-subtitle">Database Repository Pattern, Role-Based Cryptographic Access Tokens, and Production Scaling Blueprint</div></div>', unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    w1, w2 = st.columns(2)
    with w1:
        st.markdown(
            """
<div class="main-card">
  <div class="card-title">🔐 Role-Based Cryptographic Access Tokens (RBAC-PAT)</div>
  <div style="font-size:13px;color:#334155;line-height:1.7;margin-top:10px;">
    <div>• <b>Master Admin (You):</b> <code>ADM-SEC-7F9A2B81C3D4</code> — Full telemetry, ML model suite, custom parameter lab, all accounts & control triggers.</div>
    <div style="margin-top:8px;">• <b>Faculty Persona:</b> <code>FAC-SEC-5E6C1D94A8B2</code> — Departmental roster, subject grade submission, and AI traffic forecast.</div>
    <div style="margin-top:8px;">• <b>Student Persona:</b> <code>STU-SEC-3B8A7F1C9E20</code> — Scoped personal transcript, sub-millisecond cached queries, and session redirect risk meter.</div>
    <div style="background:#ECFDF5;padding:12px;border-radius:12px;margin-top:14px;color:#065F46;font-size:12px;">
      🛡️ <b>Cryptographic Security:</b> HMAC-SHA256 constant-time verification (<code>hmac.compare_digest</code>) provably prevents timing side-channel attacks.
    </div>
  </div>
</div>
            """,
            unsafe_allow_html=True,
        )

    with w2:
        st.markdown(
            """
<div class="main-card">
  <div class="card-title">🗄️ Database Adapter & PostgreSQL Migration Roadmap</div>
  <div style="font-size:13px;color:#334155;line-height:1.7;margin-top:10px;">
    <div>• <b>Development Prototype:</b> SQLite 3 with Write-Ahead Logging (<code>PRAGMA journal_mode=WAL; PRAGMA busy_timeout=5000;</code>).</div>
    <div style="margin-top:8px;">• <b>Production Migration:</b> Database Repository abstraction (<code>BaseDatabaseAdapter</code>) allows drop-in switching to PostgreSQL + PgBouncer.</div>
    <div style="margin-top:8px;">• <b>Read Replicas:</b> Query router separates high-frequency result reads to replica pools while routing grade updates to master.</div>
    <div style="background:#EFF6FF;padding:12px;border-radius:12px;margin-top:14px;color:#1E40AF;font-size:12px;">
      📈 <b>Active Backend:</b> SQLite WAL Adapter (ANSI SQL Compatible) · Ready for PostgreSQL Connection Pooling.
    </div>
  </div>
</div>
            """,
            unsafe_allow_html=True,
        )


if __name__ == "__main__":
    main()
