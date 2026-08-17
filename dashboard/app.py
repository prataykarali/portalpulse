"""PortalPulse Week 1 dashboard — dataset health, traffic, model, live simulation."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
import xgboost as xgb

ROOT = Path(__file__).resolve().parents[1]
CLEAN_PATH = ROOT / "Module1_Data" / "dataset_clean.csv"
RAW_PATH = ROOT / "team1_work" / "processed" / "dataset_raw.csv"
MODEL_PATH = ROOT / "traffic_bot_model" / "xgboost_safe_capacity.json"
META_PATH = ROOT / "traffic_bot_model" / "xgboost_metadata.json"
SCHEMA_PATH = ROOT / "traffic_bot_model" / "feature_schema.json"

FEATURES = [
    "hour",
    "day_of_week",
    "is_weekend",
    "is_result_window",
    "concurrent_users",
    "requests_per_sec",
    "cpu_usage",
    "memory_usage",
    "network_usage",
    "latency_ms",
    "error_rate",
]
DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
SLA_LATENCY = 800.0
SLA_ERROR = 0.01
SLA_CPU = 85.0

PLOT_FONT = dict(family="Inter, Segoe UI, Helvetica, Arial, sans-serif", size=13, color="#334155")
PLOTLY_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="#FFFFFF",
    font=PLOT_FONT,
    margin=dict(l=48, r=24, t=48, b=40),
    hoverlabel=dict(bgcolor="white", font_size=12, font_color="#0F172A"),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
)

PRESETS = {
    "Quiet night": {
        "hour": 3,
        "day_of_week": 1,
        "is_result_window": 0,
        "concurrent_users": 1031,
        "requests_per_sec": 129.8,
        "cpu_usage": 24.1,
        "memory_usage": 27.4,
        "network_usage": 4.6,
        "latency_ms": 41.4,
        "error_rate": 0.0005,
    },
    "Typical afternoon": {
        "hour": 12,
        "day_of_week": 0,
        "is_result_window": 0,
        "concurrent_users": 2583,
        "requests_per_sec": 314.2,
        "cpu_usage": 40.5,
        "memory_usage": 32.0,
        "network_usage": 12.1,
        "latency_ms": 38.6,
        "error_rate": 0.0017,
    },
    "Busy period": {
        "hour": 14,
        "day_of_week": 6,
        "is_result_window": 0,
        "concurrent_users": 4681,
        "requests_per_sec": 543.6,
        "cpu_usage": 58.5,
        "memory_usage": 38.4,
        "network_usage": 23.6,
        "latency_ms": 95.7,
        "error_rate": 0.0012,
    },
    "Result-day peak": {
        "hour": 14,
        "day_of_week": 4,
        "is_result_window": 1,
        "concurrent_users": 8772,
        "requests_per_sec": 1042.3,
        "cpu_usage": 100.0,
        "memory_usage": 57.3,
        "network_usage": 52.0,
        "latency_ms": 8000.0,
        "error_rate": 0.6862,
    },
}


def inject_css() -> None:
    st.markdown(
        """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

html, body, [class*="css"], .stApp, .stMarkdown, p, span, label, div {
  font-family: Inter, Segoe UI, Helvetica, Arial, sans-serif;
}

.stApp, .stApp header, [data-testid="stAppViewContainer"],
[data-testid="stHeader"], [data-testid="stToolbar"],
[data-testid="stMain"], [data-testid="stBottomBlockContainer"] {
  background: #FFFFFF !important;
}

[data-testid="stHeader"] { background: #FFFFFF !important; border-bottom: 0; }
[data-testid="stSidebar"] { background: #F8FAFC !important; border-right: 1px solid #E2E8F0; }
[data-testid="stSidebar"] * { color: #0F172A; }
.block-container { padding-top: 1.4rem; padding-bottom: 3rem; max-width: 1240px; }

#MainMenu, footer, .stDeployButton { visibility: hidden; }

.hero {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  padding: 22px 28px;
  border: 1px solid #E2E8F0;
  border-radius: 18px;
  background:
    linear-gradient(90deg, rgba(255,255,255,0.96) 0%, rgba(255,255,255,0.88) 46%, rgba(255,255,255,0.55) 100%),
    url('https://images.unsplash.com/photo-1558494949-ef010cbdcc31?auto=format&fit=crop&w=1600&q=70')
    center/cover no-repeat;
  margin-bottom: 18px;
}
.hero-kicker {
  letter-spacing: 0.16em;
  text-transform: uppercase;
  font-size: 11px;
  font-weight: 700;
  color: #1D4ED8;
  margin: 0 0 6px 0;
}
.hero h1 {
  margin: 0;
  font-size: 30px;
  font-weight: 800;
  color: #0F172A;
  letter-spacing: -0.03em;
}
.hero p { margin: 6px 0 0 0; color: #475569; font-size: 15px; }
.hero-badge {
  flex-shrink: 0;
  background: #FFFFFF;
  border: 1px solid #DBEAFE;
  color: #1D4ED8;
  font-size: 12px;
  font-weight: 700;
  padding: 8px 12px;
  border-radius: 999px;
}

.section-title {
  margin: 28px 0 12px 0;
  font-size: 18px;
  font-weight: 700;
  color: #0F172A;
  letter-spacing: -0.02em;
}
.section-sub { color: #64748B; font-size: 13.5px; margin: -6px 0 14px 0; }

.kpi-row { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin: 4px 0 8px 0; }
.kpi {
  border: 1px solid #E2E8F0;
  border-radius: 14px;
  padding: 16px 18px;
  background: #FFFFFF;
}
.kpi .label { color: #64748B; font-size: 12px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.06em; }
.kpi .value { color: #0F172A; font-size: 26px; font-weight: 800; letter-spacing: -0.03em; margin-top: 4px; }
.kpi .hint { color: #94A3B8; font-size: 12px; margin-top: 2px; }

.card {
  border: 1px solid #E2E8F0;
  border-radius: 16px;
  background: #FFFFFF;
  padding: 16px 18px 8px 18px;
  height: 100%;
}
.metric-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 10px; }
.mcard {
  border: 1px solid #E2E8F0;
  border-radius: 14px;
  padding: 14px 14px 12px 14px;
  background: #FFFFFF;
}
.mcard .ico { font-size: 16px; margin-bottom: 8px; }
.mcard .lab { color: #64748B; font-size: 12px; font-weight: 600; }
.mcard .val { color: #0F172A; font-size: 22px; font-weight: 800; letter-spacing: -0.03em; margin-top: 4px; }
.mcard .sub { color: #94A3B8; font-size: 11.5px; margin-top: 2px; }

.monitor {
  border: 1px solid #E2E8F0;
  border-radius: 18px;
  background: #FFFFFF;
  overflow: hidden;
}
.monitor-head {
  padding: 14px 18px;
  border-bottom: 1px solid #E2E8F0;
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: #1D4ED8;
  background: #F8FAFC;
}
.monitor-body { padding: 18px 20px 20px 20px; }
.mon-lab { color: #64748B; font-size: 12px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.06em; }
.mon-val { color: #0F172A; font-size: 34px; font-weight: 800; letter-spacing: -0.04em; line-height: 1.05; margin: 4px 0 16px 0; }
.mon-val.small { font-size: 22px; margin-bottom: 8px; }
.arrow { color: #CBD5E1; text-align: center; font-size: 18px; margin: -8px 0 8px 0; }

.status-pill {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  border-radius: 999px;
  padding: 8px 14px;
  font-weight: 800;
  font-size: 15px;
  letter-spacing: 0.04em;
}
.status-SAFE { background: #ECFDF5; color: #047857; border: 1px solid #A7F3D0; }
.status-AT_RISK { background: #FFFBEB; color: #B45309; border: 1px solid #FDE68A; }
.status-OVERLOADED { background: #FEF2F2; color: #B91C1C; border: 1px solid #FECACA; }

.note {
  margin-top: 10px;
  color: #64748B;
  font-size: 12.5px;
  line-height: 1.45;
}
.pipeline {
  margin-top: 28px;
  border: 1px solid #E2E8F0;
  border-radius: 14px;
  padding: 14px 16px;
  color: #475569;
  font-size: 13px;
  background: #F8FAFC;
  text-align: center;
}

[data-testid="stMetric"] {
  background: #FFFFFF;
  border: 1px solid #E2E8F0;
  border-radius: 14px;
  padding: 12px 14px;
}
[data-testid="stMetricValue"] { font-weight: 800; color: #0F172A; }
[data-testid="stMetricLabel"] { color: #64748B; }

div[data-testid="stSlider"] label, div[data-testid="stSelectbox"] label,
div[data-testid="stNumberInput"] label { font-weight: 600; color: #334155; }

.stButton > button {
  background: #1D4ED8;
  color: white;
  border: 0;
  border-radius: 10px;
  font-weight: 700;
  padding: 0.55rem 1rem;
}
.stButton > button:hover { background: #1E40AF; color: white; }

@media (max-width: 900px) {
  .metric-grid, .kpi-row { grid-template-columns: 1fr 1fr; }
  .hero { flex-direction: column; align-items: flex-start; }
}
</style>
        """,
        unsafe_allow_html=True,
    )


@st.cache_data(show_spinner=False)
def load_tables() -> tuple[pd.DataFrame, pd.DataFrame]:
    clean = pd.read_csv(CLEAN_PATH)
    clean["timestamp"] = pd.to_datetime(clean["timestamp"])
    raw = pd.read_csv(RAW_PATH)
    return clean, raw


@st.cache_data(show_spinner=False)
def load_meta() -> dict:
    with META_PATH.open() as f:
        meta = json.load(f)
    with SCHEMA_PATH.open() as f:
        schema = json.load(f)
    meta["schema"] = schema
    return meta


@st.cache_resource(show_spinner=False)
def load_model() -> xgb.Booster:
    booster = xgb.Booster()
    booster.load_model(str(MODEL_PATH))
    return booster


def predict_capacity(model: xgb.Booster, frame: pd.DataFrame) -> np.ndarray:
    ordered = frame[FEATURES].copy()
    dmat = xgb.DMatrix(ordered, feature_names=FEATURES)
    return np.asarray(model.predict(dmat), dtype=float)


def risk_from_prediction(
    users: float,
    capacity: float,
    cpu: float,
    latency: float,
    error_rate: float,
) -> tuple[str, float]:
    util = float(users) / max(float(capacity), 1.0)
    sla_breach = cpu >= SLA_CPU or latency >= SLA_LATENCY or error_rate >= SLA_ERROR
    if sla_breach or util >= 0.90:
        return "OVERLOADED", util
    if util >= 0.70:
        return "AT_RISK", util
    return "SAFE", util


def status_label(code: str) -> tuple[str, str]:
    return {
        "SAFE": ("SAFE", "Current load is inside the model's safe operating band."),
        "AT_RISK": ("HIGH", "Utilization is elevated. Headroom is shrinking."),
        "OVERLOADED": ("OVERLOAD", "Predicted capacity is exhausted or an SLA line is already breached."),
    }[code]


def apply_layout(fig: go.Figure, height: int = 340) -> go.Figure:
    fig.update_layout(**PLOTLY_LAYOUT, height=height)
    fig.update_xaxes(showgrid=True, gridcolor="#F1F5F9", zeroline=False, linecolor="#E2E8F0")
    fig.update_yaxes(showgrid=True, gridcolor="#F1F5F9", zeroline=False, linecolor="#E2E8F0")
    return fig


def dataset_health(clean: pd.DataFrame, raw: pd.DataFrame) -> dict:
    removed = int(len(raw) - len(clean))
    return {
        "raw": int(len(raw)),
        "clean": int(len(clean)),
        "removed": removed,
        "features": len(FEATURES),
        "missing": int(clean.isna().sum().sum()),
        "target": "safe_capacity",
        "risk_counts": clean["risk_level"].value_counts().to_dict(),
        "start": clean["timestamp"].min(),
        "end": clean["timestamp"].max(),
    }


@st.cache_data(show_spinner=False)
def scored_sample(seed: int = 7, n: int = 2800) -> pd.DataFrame:
    clean, _ = load_tables()
    model = load_model()
    sample = clean.sample(n=min(n, len(clean)), random_state=seed).copy()
    sample["predicted_capacity"] = predict_capacity(model, sample)
    return sample


def render_header(meta: dict, health: dict) -> None:
    st.markdown(
        """
<div class="hero">
  <div>
    <p class="hero-kicker">PortalPulse · Module 1</p>
    <h1>AI Traffic Intelligence</h1>
    <p>Can the model read load conditions on an IEM-style result portal?</p>
  </div>
  <div class="hero-badge">Week 1 prototype</div>
</div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        f"""
<div class="kpi-row">
  <div class="kpi">
    <div class="label">Dataset</div>
    <div class="value">{health['clean']:,}</div>
    <div class="hint">clean minute-level records</div>
  </div>
  <div class="kpi">
    <div class="label">Features</div>
    <div class="value">{health['features']}</div>
    <div class="hint">inputs the model actually uses</div>
  </div>
  <div class="kpi">
    <div class="label">Model</div>
    <div class="value">{meta['model']}</div>
    <div class="hint">{meta['task']} · target {meta['target']}</div>
  </div>
</div>
        """,
        unsafe_allow_html=True,
    )


def render_dataset_health(health: dict, clean: pd.DataFrame) -> None:
    st.markdown('<div class="section-title">1. Dataset health</div>', unsafe_allow_html=True)
    st.markdown(
        '<p class="section-sub">Team 1 prepared one master table. These numbers are counted from the CSVs on disk.</p>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f"""
<div class="metric-grid">
  <div class="mcard"><div class="ico">📊</div><div class="lab">Raw records</div>
    <div class="val">{health['raw']:,}</div><div class="sub">before cleaning</div></div>
  <div class="mcard"><div class="ico">🧹</div><div class="lab">Clean records</div>
    <div class="val">{health['clean']:,}</div><div class="sub">39,584 × 14 columns</div></div>
  <div class="mcard"><div class="ico">❌</div><div class="lab">Removed / invalid</div>
    <div class="val">{health['removed']:,}</div><div class="sub">dupes, sensor faults, dropouts</div></div>
  <div class="mcard"><div class="ico">🔢</div><div class="lab">Features</div>
    <div class="val">{health['features']}</div><div class="sub">missing values: {health['missing']}</div></div>
  <div class="mcard"><div class="ico">🎯</div><div class="lab">Target variable</div>
    <div class="val" style="font-size:18px;padding-top:6px;">safe_capacity</div>
    <div class="sub">max users before SLA breach</div></div>
</div>
        """,
        unsafe_allow_html=True,
    )

    c1, c2 = st.columns([1.15, 1])
    with c1:
        risk = (
            clean["risk_level"]
            .value_counts()
            .reindex(["SAFE", "AT_RISK", "OVERLOADED"])
            .fillna(0)
            .reset_index()
        )
        risk.columns = ["risk_level", "minutes"]
        fig = px.bar(
            risk,
            x="risk_level",
            y="minutes",
            color="risk_level",
            color_discrete_map={"SAFE": "#10B981", "AT_RISK": "#F59E0B", "OVERLOADED": "#EF4444"},
            title="Risk-level mix in the clean table",
        )
        fig.update_layout(showlegend=False)
        fig.update_traces(marker_line_width=0, width=0.55)
        st.plotly_chart(apply_layout(fig, 320), use_container_width=True)
    with c2:
        start = health["start"].strftime("%d %b %Y %H:%M")
        end = health["end"].strftime("%d %b %Y %H:%M")
        st.markdown(
            f"""
<div class="card" style="padding:18px 20px 16px 20px;">
  <div style="font-weight:700;margin-bottom:10px;">What Team 1 handed over</div>
  <div style="color:#334155;font-size:13.5px;line-height:1.55;">
    <div><b>Window:</b> {start} → {end}</div>
    <div><b>Grain:</b> one row = one minute</div>
    <div><b>Result-window minutes:</b> {int(clean['is_result_window'].sum()):,}</div>
    <div><b>Risk mix:</b> SAFE {health['risk_counts'].get('SAFE', 0):,} · AT_RISK {health['risk_counts'].get('AT_RISK', 0):,} · OVERLOADED {health['risk_counts'].get('OVERLOADED', 0):,}</div>
    <div style="margin-top:10px;">Cleaning removed 18 duplicate rows, 10 impossible sensor rows, and 99 monitoring dropouts.</div>
    <div style="margin-top:8px;color:#64748B;">Demand shape is real NASA HTTP traffic, scaled to ERP-like user counts. CPU / RAM / capacity labels come from a documented resource model — not a live IEM dump.</div>
  </div>
</div>
            """,
            unsafe_allow_html=True,
        )


def render_traffic(clean: pd.DataFrame) -> None:
    st.markdown('<div class="section-title">2. Traffic / load visualization</div>', unsafe_allow_html=True)
    st.markdown(
        '<p class="section-sub">When traffic rises, CPU and latency follow. Result-day minutes sit on a lower capacity floor.</p>',
        unsafe_allow_html=True,
    )

    hourly = (
        clean.set_index("timestamp")
        .resample("h")
        .agg(
            concurrent_users=("concurrent_users", "mean"),
            cpu_usage=("cpu_usage", "mean"),
            latency_ms=("latency_ms", "mean"),
            requests_per_sec=("requests_per_sec", "mean"),
            error_rate=("error_rate", "mean"),
        )
        .dropna()
        .reset_index()
    )

    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(
        go.Scatter(
            x=hourly["timestamp"],
            y=hourly["concurrent_users"],
            name="Concurrent users",
            line=dict(color="#2563EB", width=2),
            fill="tozeroy",
            fillcolor="rgba(37,99,235,0.08)",
        ),
        secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(
            x=hourly["timestamp"],
            y=hourly["cpu_usage"],
            name="CPU %",
            line=dict(color="#7C3AED", width=1.6),
        ),
        secondary_y=True,
    )
    fig.update_yaxes(title_text="Concurrent users", secondary_y=False)
    fig.update_yaxes(title_text="CPU utilization %", secondary_y=True, range=[0, 100])
    fig.update_layout(title="Hourly traffic vs CPU")
    st.plotly_chart(apply_layout(fig, 380), use_container_width=True)

    left, right = st.columns(2)
    sample = clean.sample(n=min(4500, len(clean)), random_state=11)
    with left:
        fig = px.scatter(
            sample,
            x="concurrent_users",
            y="latency_ms",
            color="risk_level",
            color_discrete_map={"SAFE": "#10B981", "AT_RISK": "#F59E0B", "OVERLOADED": "#EF4444"},
            opacity=0.45,
            title="Users vs latency — the stress knee",
        )
        fig.add_hline(y=SLA_LATENCY, line_dash="dash", line_color="#94A3B8", annotation_text="SLA 800 ms")
        fig.update_traces(marker=dict(size=6))
        st.plotly_chart(apply_layout(fig, 360), use_container_width=True)
    with right:
        by_hour = clean.groupby("hour", as_index=False).agg(
            users=("concurrent_users", "mean"),
            cpu=("cpu_usage", "mean"),
        )
        fig = go.Figure()
        fig.add_trace(
            go.Bar(x=by_hour["hour"], y=by_hour["users"], name="Avg users", marker_color="#93C5FD")
        )
        fig.add_trace(
            go.Scatter(
                x=by_hour["hour"],
                y=by_hour["cpu"],
                name="Avg CPU %",
                yaxis="y2",
                line=dict(color="#7C3AED", width=2.4),
            )
        )
        fig.update_layout(
            title="Average load by hour of day",
            yaxis=dict(title="Users"),
            yaxis2=dict(title="CPU %", overlaying="y", side="right", range=[0, 100]),
            xaxis=dict(title="Hour", dtick=2),
            barmode="overlay",
        )
        st.plotly_chart(apply_layout(fig, 360), use_container_width=True)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Peak concurrent users", f"{int(clean['concurrent_users'].max()):,}")
    c2.metric("Median users", f"{int(clean['concurrent_users'].median()):,}")
    c3.metric("Median latency", f"{clean['latency_ms'].median():.0f} ms")
    c4.metric("Minutes with errors ≥ 1%", f"{int((clean['error_rate'] >= SLA_ERROR).sum()):,}")


def render_model(meta: dict, scored: pd.DataFrame) -> None:
    st.markdown('<div class="section-title">3. AI model performance</div>', unsafe_allow_html=True)
    st.markdown(
        '<p class="section-sub">Team 2 trained an XGBoost regressor that predicts safe capacity from the 11 traffic / telemetry features.</p>',
        unsafe_allow_html=True,
    )

    test = meta["test_metrics"]
    val = meta["validation_metrics"]
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Test MAE", f"{test['MAE']:.1f}", help="Mean absolute error on the untouched test set, in users.")
    m2.metric("Test RMSE", f"{test['RMSE']:.1f}")
    m3.metric("Test R²", f"{test['R2']:.3f}")
    m4.metric("Validation R²", f"{val['R2']:.3f}")

    left, right = st.columns([1.2, 1])
    with left:
        lo = min(scored["safe_capacity"].min(), scored["predicted_capacity"].min())
        hi = max(scored["safe_capacity"].max(), scored["predicted_capacity"].max())
        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=scored["safe_capacity"],
                y=scored["predicted_capacity"],
                mode="markers",
                marker=dict(size=6, color="#2563EB", opacity=0.35),
                name="Sample minutes",
            )
        )
        fig.add_trace(
            go.Scatter(
                x=[lo, hi],
                y=[lo, hi],
                mode="lines",
                line=dict(color="#94A3B8", dash="dash"),
                name="Perfect fit",
            )
        )
        fig.update_layout(
            title="Actual vs predicted safe capacity (sample)",
            xaxis_title="Actual safe_capacity",
            yaxis_title="Model prediction",
        )
        st.plotly_chart(apply_layout(fig, 380), use_container_width=True)
    with right:
        model = load_model()
        gain = model.get_score(importance_type="gain")
        imp = pd.DataFrame({"feature": list(gain.keys()), "gain": list(gain.values())})
        imp["share"] = 100 * imp["gain"] / imp["gain"].sum()
        imp = imp.sort_values("share", ascending=True)
        fig = px.bar(
            imp,
            x="share",
            y="feature",
            orientation="h",
            title="Feature importance (% of total gain)",
        )
        fig.update_traces(marker_color="#1D4ED8", hovertemplate="%{y}: %{x:.2f}%<extra></extra>")
        fig.update_layout(xaxis_title="Share of gain (%)", yaxis_title="", xaxis_type="log")
        st.plotly_chart(apply_layout(fig, 380), use_container_width=True)

    st.caption(
        "Official metrics come from `traffic_bot_model/xgboost_metadata.json`. "
        "The scatter is a cached sample scored live by the saved booster — not a second training run. "
        "MAE / RMSE are in concurrent-user units."
    )


def default_inputs() -> dict:
    return dict(PRESETS["Typical afternoon"])


def collect_inputs() -> dict:
    if "inputs" not in st.session_state:
        st.session_state.inputs = default_inputs()

    st.markdown("**Scenario presets**")
    preset_labels = {
        "Quiet night": "Quiet",
        "Typical afternoon": "Typical",
        "Busy period": "Busy",
        "Result-day peak": "Result day",
    }
    cols = st.columns(len(PRESETS))
    for col, name in zip(cols, PRESETS):
        if col.button(preset_labels[name], use_container_width=True, help=name):
            st.session_state.inputs = dict(PRESETS[name])
            st.rerun()

    current = st.session_state.inputs
    left, right = st.columns(2)
    with left:
        users = st.slider("Concurrent users", 50, 12500, int(current["concurrent_users"]), 25)
        rps = st.slider("Requests / sec", 5.0, 1800.0, float(current["requests_per_sec"]), 5.0)
        cpu = st.slider("CPU utilization %", 0.0, 100.0, float(current["cpu_usage"]), 0.5)
        mem = st.slider("Memory utilization %", 0.0, 100.0, float(current["memory_usage"]), 0.5)
        net = st.slider("Network utilization %", 0.0, 100.0, float(current["network_usage"]), 0.5)
    with right:
        latency = st.slider("Latency (ms)", 15.0, 8000.0, float(current["latency_ms"]), 5.0)
        err = st.slider("Error rate", 0.0, 0.70, float(current["error_rate"]), 0.0005, format="%.4f")
        hour = st.slider("Hour of day", 0, 23, int(current["hour"]))
        day = st.selectbox(
            "Day of week",
            options=list(range(7)),
            index=int(current["day_of_week"]),
            format_func=lambda i: DAY_NAMES[i],
        )
        result = st.toggle("Result / announcement window", value=bool(current["is_result_window"]))

    return {
        "hour": hour,
        "day_of_week": int(day),
        "is_weekend": int(day >= 5),
        "is_result_window": int(result),
        "concurrent_users": int(users),
        "requests_per_sec": float(rps),
        "cpu_usage": float(cpu),
        "memory_usage": float(mem),
        "network_usage": float(net),
        "latency_ms": float(latency),
        "error_rate": float(err),
    }


def render_status(model: xgb.Booster) -> None:
    st.markdown('<div class="section-title">4. Traffic status · live simulation</div>', unsafe_allow_html=True)
    st.markdown(
        '<p class="section-sub">Type a traffic snapshot. The saved model returns estimated safe capacity, then we map utilization to a status. This is not connected to the live IEM portal.</p>',
        unsafe_allow_html=True,
    )

    form, panel = st.columns([1.15, 0.85])
    with form:
        inputs = collect_inputs()
        row = pd.DataFrame([inputs])
        capacity = float(predict_capacity(model, row)[0])
        code, util = risk_from_prediction(
            inputs["concurrent_users"],
            capacity,
            inputs["cpu_usage"],
            inputs["latency_ms"],
            inputs["error_rate"],
        )
        short, blurb = status_label(code)
        load_pct = util * 100.0

    with panel:
        st.markdown(
            f"""
<div class="monitor">
  <div class="monitor-head">PortalPulse AI monitor</div>
  <div class="monitor-body">
    <div class="mon-lab">Current traffic</div>
    <div class="mon-val">{inputs['concurrent_users']:,} <span style="font-size:16px;color:#64748B;font-weight:600;">users</span></div>
    <div class="arrow">↓</div>
    <div class="mon-lab">Predicted load</div>
    <div class="mon-val">{load_pct:.0f}%</div>
    <div class="arrow">↓</div>
    <div class="mon-lab">Status</div>
    <div class="mon-val small"><span class="status-pill status-{code}">{short}</span></div>
    <div class="mon-lab" style="margin-top:18px;">Model-estimated capacity</div>
    <div class="mon-val small">{capacity:,.0f} concurrent users</div>
    <p class="note">{blurb}<br>Prototype estimate based on the trained model and the available dataset — not a live measurement of the IEM portal.</p>
  </div>
</div>
            """,
            unsafe_allow_html=True,
        )

    a, b, c = st.columns(3)
    a.metric("Predicted safe capacity", f"{capacity:,.0f}")
    b.metric("Utilization", f"{load_pct:.1f}%")
    headroom = max(capacity - inputs["concurrent_users"], 0)
    c.metric("Estimated remaining headroom", f"{headroom:,.0f} users")

    sla_bits = []
    sla_bits.append("CPU " + ("breached" if inputs["cpu_usage"] >= SLA_CPU else "ok"))
    sla_bits.append("latency " + ("breached" if inputs["latency_ms"] >= SLA_LATENCY else "ok"))
    sla_bits.append("errors " + ("breached" if inputs["error_rate"] >= SLA_ERROR else "ok"))
    st.caption(
        "Status rule: utilization = current users ÷ predicted capacity. "
        "SAFE < 70% · HIGH 70–90% · OVERLOAD ≥ 90% or any SLA breach "
        f"(CPU ≥ {SLA_CPU:.0f}%, latency ≥ {SLA_LATENCY:.0f} ms, error rate ≥ 1%). "
        + " · ".join(sla_bits)
        + "."
    )


def main() -> None:
    st.set_page_config(
        page_title="PortalPulse · Week 1",
        page_icon="📡",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    inject_css()

    missing = [p for p in (CLEAN_PATH, RAW_PATH, MODEL_PATH, META_PATH) if not p.exists()]
    if missing:
        st.error("Required files are missing:\n" + "\n".join(f"- `{p}`" for p in missing))
        st.stop()

    clean, raw = load_tables()
    meta = load_meta()
    model = load_model()
    health = dataset_health(clean, raw)
    scored = scored_sample()

    render_header(meta, health)
    render_dataset_health(health, clean)
    render_traffic(clean)
    render_model(meta, scored)
    render_status(model)

    st.markdown(
        """
<div class="pipeline">
  Team 1 raw dataset → cleaning / preprocessing → clean dataset → Team 2 XGBoost
  → prediction → Week 1 dashboard → traffic status · load risk · capacity estimate
</div>
        """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
