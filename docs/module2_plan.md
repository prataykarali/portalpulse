# PortalPulse Module 2: Prediction, Decision Engine & Real-Time Traffic Simulation

## Executive Summary & Engineering Objective

> **Module 2 Milestone Definition:**
> *"Build a realistic, telemetry-consistent predictive traffic intelligence layer that converts simulated IEMCRP demand into system-state predictions and explainable traffic-risk decisions."*

In **Module 1**, the team established the data and ML foundation: cleaning 39,584 minute-level records, freezing train/validation/test splits, establishing the 800ms / 85% CPU / 1% error SLA definitions, and training baseline XGBoost models.

In **Module 2**, PortalPulse transitions from static dataset analysis into a **real-time predictive and decision-making system**. It observes coupled server telemetry, forecasts approaching capacity limits across nonlinear latency saturation curves, and outputs deterministic, explainable control actions (`SAFE`, `WARNING`, `CRITICAL`).

---

## 1. Architectural Blueprint

```
                    ┌──────────────────────────────┐
                    │      OPERATIONAL SCENARIO    │
                    │   (Result Rush, Exam Fees,   │
                    │     Course Reg, Regular)     │
                    └──────────────┬───────────────┘
                                   │
                                   ▼
                    ┌──────────────────────────────┐
                    │      TRAFFIC SIMULATOR       │
                    │  (Concurrent User Demand X)  │
                    └──────────────┬───────────────┘
                                   │
                                   ▼
                    ┌──────────────────────────────┐
                    │    TELEMETRY SYNTHESIZER     │
                    │  • Requests/sec (RPS)        │
                    │  • CPU / RAM / Network       │
                    │  • Latency Queuing Knee      │
                    │  • Estimated Error Rate      │
                    └──────────────┬───────────────┘
                                   │
                                   ▼
                    ┌──────────────────────────────┐
                    │    FEATURE EXTRACTION &      │
                    │       PREDICTION API         │
                    │  • Safe Capacity (SLA limit) │
                    │  • Expected Latency & CPU    │
                    └──────────────┬───────────────┘
                                   │
                                   ▼
                    ┌──────────────────────────────┐
                    │   DETERMINISTIC DECISION     │
                    │           ENGINE             │
                    │  • SAFE (<70% util)          │
                    │  • WARNING (70–90% util)     │
                    │  • CRITICAL (≥90% / breach)  │
                    └──────────────┬───────────────┘
                                   │
                ┌──────────────────┴──────────────────┐
                ▼                                     ▼
     ┌──────────────────────┐              ┌──────────────────────┐
     │    LIVE MONITORING   │              │   TRAFFIC CONTROL    │
     │      DASHBOARD       │              │   ACTION SKELETON    │
     │  • 5 Core Questions  │              │  • Normal Ingestion  │
     │  • Operating Curves  │              │  • Prepare Queueing  │
     │  • Headroom Meters   │              │  • Protection Mode   │
     └──────────────────────┘              └──────────────────────┘
```

---

## 2. Topic Mapping & Syllabus Alignment

| # | Topic | What You Learn | What We Build in Module 2 |
|---|---|---|---|
| **1** | **Model Evaluation** | MAE, RMSE, $R^2$, Residual distribution, Imbalanced classification evaluation | Multi-target evaluation suite for `safe_capacity`, latency, and CPU |
| **2** | **Inference / Prediction** | Packaging model weights for low-latency scoring from live telemetry | High-throughput Prediction API / inference function |
| **3** | **Feature Engineering** | Dynamic feature extraction, rolling statistics, calendar event encoding | Telemetry feature pipeline transforming raw traffic into model inputs |
| **4** | **Thresholds & Decision Logic** | Translating continuous ML predictions into operational decisions | Deterministic Rule-Based Decision Engine (`SAFE`, `WARNING`, `CRITICAL`) |
| **5** | **Load Simulation** | Synthetic workload modeling, nonlinear queuing saturation knees | Interactive Scenario-driven Traffic Simulator |
| **6** | **Backend Integration** | Connecting telemetry input $\rightarrow$ feature extraction $\rightarrow$ model $\rightarrow$ decision | Unified Python backend pipeline |
| **7** | **Real-Time Monitoring** | Visualizing capacity headroom, operating points, and risk states | Interactive Streamlit / Web Live Monitoring Panel |
| **8** | **Anomaly & Spike Detection** | Detecting out-of-distribution traffic surges and flash spikes | Flash-crowd indicator comparing observed vs historical baselines |

---

## 3. Four Core System Components

### Component 1: Prediction API
- **Inputs**: Observed active sessions, arrival rate (RPS), CPU utilization, RAM usage, network bandwidth, and calendar scenario context.
- **Model**: Trained XGBoost / LightGBM Multi-Output Regressor (`team2_work/scripts/train_multi_output.py`).
- **Outputs**:
  1. `safe_capacity`: Max concurrent active users sustainable under strict SLA ($p95 \text{ latency} < 800\text{ms}, \text{CPU} < 85\%, \text{error} < 1\%$).
  2. `predicted_latency_ms`: Expected service response time under the current traffic footprint.
  3. `predicted_cpu_usage`: Expected processor load.

### Component 2: Deterministic Decision Engine
ML predictions provide statistical estimates, but **operational control requires deterministic rules**. The decision engine ensures explainability and safety:
- **`SAFE` (Normal Ingestion)**:
  $$\text{Utilization} = \frac{\text{Current Users}}{\text{Safe Capacity}} < 0.70 \quad \text{and no SLA breaches}$$
  *Action:* Standard traffic throughput.
- **`WARNING` (Prepare Traffic Controls)**:
  $$0.70 \le \text{Utilization} < 0.90 \quad \text{and no SLA breaches}$$
  *Action:* Arm virtual waiting room, warm cache, alert operators.
- **`CRITICAL` (Emergency Traffic Protection)**:
  $$\text{Utilization} \ge 0.90 \quad \text{OR} \quad \text{CPU} \ge 85\% \quad \text{OR} \quad \text{Latency} \ge 800\text{ms}$$
  *Action:* Activate token-bucket admission, prioritize final-year student sessions, queue incoming requests.

### Component 3: Intelligent Traffic Simulator
Replaces disjoint sliders with a **coupled synthetic workload model**:
- **Scenario Profiles**:
  - `Regular Academic Day`: Stable load, routine LMS access, normal query complexity (~3,200 users).
  - `Result Declaration Rush`: Flash spike, heavy DB join queries, high un-cached result lookups (~10,500 users).
  - `Exam Fee Registration`: Sustained transactional load with DB row locking and payment gateway handoffs (~7,600 users).
  - `Course Registration Rush`: Immediate burst concurrency and seat lock contention (~8,800 users).
  - `Off-Peak Night`: Low baseline maintenance (~650 users).
- **Physical Coupling**:
  - Linear/sub-linear requests/sec based on calibrated scenario arrival intensity.
  - Nonlinear M/M/1-like queuing latency curve: flat baseline (~35–65ms) up to the saturation knee, surging nonlinearly past 800ms into seconds during overload.
  - Estimated error rate modeled as an **outcome** of SLA degradation, never as an artificial user slider.

### Component 4: Live Monitoring Dashboard
Answers the **5 Critical Operational Questions** in real-time:
1. **How much traffic is incoming?** $\rightarrow$ Active concurrent sessions.
2. **How much can we safely handle?** $\rightarrow$ ML-predicted SLA Safe Capacity.
3. **How close are we to the breaking point?** $\rightarrow$ Capacity Utilization % & Remaining Headroom.
4. **What does PortalPulse forecast?** $\rightarrow$ Risk state (`SAFE`, `WARNING`, `CRITICAL`) & predicted latency.
5. **What should the system execute?** $\rightarrow$ Deterministic traffic protection action.

---

## 4. Architectural Positioning: PortalPulse vs Edge CDNs (Cloudflare)

```
             ┌──────────────────────────────────────────────┐
             │            INTERNET TRAFFIC                  │
             └──────────────────────┬───────────────────────┘
                                    │
                                    ▼
             ┌──────────────────────────────────────────────┐
             │       EDGE CDN & WAF (Cloudflare)            │
             │  • L3/L4 DDoS Mitigation                     │
             │  • Static Asset Caching (JS/CSS/Images)      │
             │  • Generic IP-based Rate Limiting            │
             └──────────────────────┬───────────────────────┘
                                    │ (Dynamic Un-cached Logins)
                                    ▼
             ┌──────────────────────────────────────────────┐
             │   PORTALPULSE PREDICTIVE INTELLIGENCE        │
             │  • Application & State-Aware Capacity Model  │
             │  • Predicts DB Connection Pool Saturation    │
             │  • Student Session Prioritization & Queuing  │
             └──────────────────────┬───────────────────────┘
                                    │ (Regulated Safe Load)
                                    ▼
             ┌──────────────────────────────────────────────┐
             │         IEMCRP MONOLITHIC ERP & DB           │
             │  • Relational DB Tables & Session Store      │
             │  • Protected from Connection Starvation      │
             └──────────────────────────────────────────────┘
```

### Why Cloudflare Alone Cannot Prevent ERP Outages:
- **Cloudflare's Domain**: Operates at the network perimeter. It excels at filtering botnets and serving cached static files.
- **The Monolithic ERP Vulnerability**: During result declaration or exam registration, every student request is dynamic, transactional, and un-cacheable (e.g. querying student roll numbers against relational tables).
- **The Consequence**: Cloudflare forwards all 10,000 legitimate HTTP requests directly to the origin backend. Without PortalPulse, the database connection pool is overwhelmed in seconds, thread starvation occurs, and the server crashes.
- **PortalPulse's Unique Role**: PortalPulse is an **application-aware predictive governor**. It understands backend database saturation limits, predicts impending failure minutes before SLA collapse, and throttles/queues at the application boundary to keep the core database healthy.

---

## 5. Team Division & Responsibilities

### 🧠 Team 1 — ML & Feature Pipeline
- **Ownership**: Data prep, feature extraction, multi-target model training, validation metrics, and model artifact exports.
- **Deliverables**:
  - Multi-target XGBoost/LightGBM model predicting `[safe_capacity, latency_ms, cpu_usage]`.
  - Feature transformer pipeline enforcing locked feature schemas.
  - Evaluation reporting (MAE, RMSE, $R^2$, residual plots).

### ⚙️ Team 2 — Backend & Decision Engine
- **Ownership**: Prediction API, deterministic decision logic, SLA threshold rules, and control action triggers.
- **Deliverables**:
  - Clean Python inference interface `predict_system_state(telemetry_dict)`.
  - Deterministic Decision Engine mapping continuous outputs to discrete states (`SAFE`, `WARNING`, `CRITICAL`).
  - Action trigger skeleton for virtual waiting room / queueing.

### 🖥️ Team 3 — Dashboard & Traffic Simulator
- **Ownership**: Scenario profiles, coupled telemetry synthesizer, capacity gauges, operating curve visualization, and live Streamlit UI.
- **Deliverables**:
  - Upgraded Streamlit dashboard answering the 5 core operational questions.
  - Interactive latency knee operating curve.
  - Scenario selector eliminating artificial toggles and isolated sliders.

---

## 6. Demonstration & Acceptance Criteria

At the Module 2 presentation, the team will demonstrate:
1. Selecting **Result Declaration Rush** with 4,000 users $\rightarrow$ Telemetry displays 480 RPS, 42% CPU, 45ms latency $\rightarrow$ Status: `🟢 SAFE`.
2. Increasing demand to 8,000 users $\rightarrow$ Telemetry displays 1,120 RPS, 76% CPU, 180ms latency $\rightarrow$ Safe Capacity predicted at 8,200 users $\rightarrow$ Utilization 97% $\rightarrow$ Status: `🟡 WARNING: PREPARE QUEUING`.
3. Increasing demand to 11,500 users $\rightarrow$ Telemetry enters saturation knee, latency surges past 800ms SLA, CPU hits 98% $\rightarrow$ Status: `🔴 CRITICAL: EMERGENCY TRAFFIC PROTECTION ACTIVATED`.
