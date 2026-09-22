# PortalPulse System Architecture & Technical Specification

> **Autonomous Resilience & Closed-Loop Operations Platform for Mission-Critical Portals**  
> *Production Reference Documentation (Modules 1–15)*

---

## 1. Architectural Overview & Component Taxonomy

PortalPulse operates as an autonomous, closed-loop control plane designed for high-concurrency portals (such as university exam portals like IEMCRP, railway reservation systems like Nirantar, and public utility portals).

To ensure complete production integrity, the system strictly demarcates **real ML models**, **deterministic safety rules**, **simulation/digital-twin infrastructure**, **backend services**, and **frontend visualization**:

| System Component | Module | Execution Type | Underlying Implementation | Artifact / Runtime File |
| :--- | :--- | :--- | :--- | :--- |
| **Telemetry Ingestion & Ring Buffer** | M1 | Live Backend Service & Deterministic Math | In-Memory `collections.deque` (1800-entry ring buffer) + SQLite WAL (`telemetry_history.db`) | `backend/m1_monitoring/collector.py` |
| **Multi-Horizon Load Forecaster** | M2 | **Trained Machine Learning Model** | Multi-target XGBoost Regressor (`+5m`, `+10m`, `+15m` Horizons, CPI) | `backend/m2_prediction/models/xgboost_forecaster.pkl` |
| **Unsupervised Anomaly Detector** | M3 | **Trained Machine Learning Model** | Scikit-learn `IsolationForest` (8-dimensional feature space, normalized score `[0.0, 1.0]`) | `backend/m3_anomaly_rca/models/isolation_forest.pkl` |
| **Root Cause Analysis (RCA) Classifier** | M4 | **Trained Machine Learning Model** | Multi-class XGBoost Classifier (8 failure categories) | `backend/m3_anomaly_rca/models/xgboost_rca.pkl` |
| **Causal Dependency DAG** | M4 | Deterministic Graph Algorithm | NetworkX `DiGraph` (Topological propagation tracing & active causal path isolation) | `backend/m3_anomaly_rca/dependency_graph.py` |
| **Tactical Action Policy** | M5 | **Trained Machine Learning Model** | Deep PyTorch Multi-Layer Perceptron (`ActionPolicyMLP`, Softmax across 11 discrete actions) | `backend/m4_action_intelligence/models/action_mlp_policy.pt` |
| **Operational Safety Guardrails** | M6 | Deterministic Rules Engine | Token Bucket rate limiter, Circuit Breaker state machine, Flapping Cooldown (300s), HITL Approval Gate | `backend/m6_safety_layer/guardrails.py` |
| **Closed-Loop Actuator** | M7 | **Simulation / Digital-Twin Middleware** | Actuator mutating session middleware (`GLOBAL_SESSION_TRACKER`), computing real before/after deltas & 5-phase trajectory | `backend/m7_actuator/actuator.py` |
| **Autonomous Control Loop** | Control Plane | Live Asynchronous Service | `asyncio` background task running 5-second control cycles, state orchestration & recovery | `backend/control_plane/control_loop.py` |
| **Traffic Engine & Swarm** | Simulation | Digital-Twin Load Generator | Locust-compatible Poisson & Result-Day traffic phase controller (`TRAFFIC_CONTROLLER`) | `backend/simulation/traffic_controller.py` |
| **Real-Time Event Streaming** | Streaming | Live Server-Sent Events (SSE) | Async unbounded-subscriber / bounded-buffer SSE broadcaster with Last-Event-ID replay | `backend/streaming/broadcaster.py` |
| **Command Center UI** | UI | Frontend Visualization | Pure Web Standards (HTML5 / Vanilla JS / CSS3), zero-alert, rolling 60-second SVG charts | `website/index.html`, `website/app.js` |

> [!NOTE]  
> **Actuator Clarification**: The M7 Actuator is a **Digital-Twin / Local Process Actuator**. It interacts directly with the connected portal's SDK middleware (e.g. enabling virtual waiting rooms, adjusting token buckets, tripping circuit breakers, shedding queue load) and simulates resource relief via deterministic telemetry transfer functions. It does not invoke cloud hypervisor or Kubernetes cloud APIs directly.

---

## 2. Seven Core Architecture Diagrams

### Diagram 1: Overall Closed-Loop Control Tower Architecture

```
                  ┌─────────────────────────────────┐
                  │    IEMCRP Exam Result Portal    │
                  │   Result-Day Concurrency Surge  │
                  └────────────────┬────────────────┘
                                   │
                                   ▼
                  ┌─────────────────────────────────┐
                  │   M1 Telemetry Ingestion Engine │
                  │  Ring Buffer + Feature Pipeline │
                  └────────────────┬────────────────┘
                                   │
                                   ▼
                  ┌─────────────────────────────────┐
                  │    M2 Multi-Horizon Forecaster  │
                  │   Trained XGBoost Regressor     │
                  └────────────────┬────────────────┘
                                   │
                                   ▼
                  ┌─────────────────────────────────┐
                  │  M3 Unsupervised Anomaly Engine │
                  │     Isolation Forest [0, 1]     │
                  └────────────────┬────────────────┘
                                   │
                                   ▼
                  ┌─────────────────────────────────┐
                  │      M4 Root Cause Analysis     │
                  │  XGBoost Classifier + Nx DAG    │
                  └────────────────┬────────────────┘
                                   │
                                   ▼
                  ┌─────────────────────────────────┐
                  │   M5 Tactical Action Policy     │
                  │    Deep PyTorch MLP (11 SRE)    │
                  └────────────────┬────────────────┘
                                   │
                                   ▼
                  ┌─────────────────────────────────┐
                  │   M6 Deterministic Safety Layer │
                  │ Cooldown, Token Bucket, Guard   │
                  └────────────────┬────────────────┘
                                   │
                                   ▼
                  ┌─────────────────────────────────┐
                  │    M7 Closed-Loop Actuator      │
                  │  SDK Middleware Intervention    │
                  └────────────────┬────────────────┘
                                   │
                                   ▼
                       CHANGED SYSTEM STATE
                  (Relieved DB Pool / Lower p95)
                                   │
                                   └──────────────→ FEEDBACK TO M1 TELEMETRY
```

---

### Diagram 2: M1 Telemetry & Feature Extraction Pipeline

```
Raw Telemetry Stream (RPS, Latency, CPU, RAM, DB Connections, Queue Length, Error Rate)
    │
    ▼
┌────────────────────────────────────────────────────────┐
│             In-Memory Ring Buffer (1,800 entries)      │
│        Thread-Safe Circular Deque (30-min window)      │
└───────────────────────────┬────────────────────────────┘
                            │
            ┌───────────────┴───────────────┐
            ▼                               ▼
┌───────────────────────────┐   ┌───────────────────────────┐
│ Real-Time Derived Feats   │   │ SQLite WAL Persistence    │
│ - rolling_mean_5m         │   │ `telemetry_history.db`    │
│ - rolling_std_5m          │   │ WAL mode, synchronous=NORM│
│ - rate_of_change (deriv)  │   │ SLA breach index          │
│ - error_rate_acceleration │   └───────────────────────────┘
└───────────┬───────────────┘
            │
            ▼
Standardized Input Vector Schema
(Ready for M2 Forecasting & M3 Anomaly Detection)
```

---

### Diagram 3: M2 XGBoost Multi-Horizon Forecasting Pipeline

```
Incoming Telemetry & Engineered Lag Features
    │
    ▼
┌────────────────────────────────────────────────────────┐
│               Feature Standardizer & Vectorizer        │
│    (active_users, requests_per_sec, cpu, ram, db_pool) │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│     XGBoost Multi-Target Regressor (`forecaster.pkl`)  │
│         Tree depth=6, n_estimators=100, lr=0.05        │
└───────────┬───────────────────┬───────────────────┬────┘
            │                   │                   │
            ▼                   ▼                   ▼
      Horizon: +5m        Horizon: +10m       Horizon: +15m
     (Predicted RPS,     (Predicted RPS,     (Predicted RPS,
      p95, CPU, DB)       p95, CPU, DB)       p95, CPU, DB)
            │                   │                   │
            └───────────────────┼───────────────────┘
                                │
                                ▼
         Capacity Pressure Index (CPI) Calculator
         Safe Capacity: 13,200 VUs | Threshold: 80%
                                │
                                ▼
                  `ForecastResult` Pydantic Payload
              (TimeToBreach: "~7 min", RiskLevel: HIGH)
```

---

### Diagram 4: M3 Isolation Forest Anomaly Detection Pipeline

```
Live System Metric Vector (8 Dimensions):
[cpu_percent, ram_percent, requests_per_sec, response_time, error_rate, db_latency, db_connections, queue_length]
    │
    ▼
┌────────────────────────────────────────────────────────┐
│        Nominal SLA Baseline Standardizer (Z-Score)     │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│  Isolation Forest Unsupervised Model (`isolation_forest.pkl`)
│             n_estimators=120, contamination=0.08       │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
           Raw Decision Function Inversion:
           Score = clamp((0.5 - decision_function) * 1.5, 0.0, 1.0)
                            │
            ┌───────────────┴───────────────┐
            ▼                               ▼
  Continuous Anomaly Score          Top Deviation Contributors
   - NOMINAL (< 0.45)               Rank-ordered by relative
   - ELEVATED (0.45 - 0.70)         Z-score deviation:
   - WARNING (0.70 - 0.85)          1. db_connections (+4.2σ)
   - CRITICAL (>= 0.85)             2. response_time (+3.8σ)
```

---

### Diagram 5: M4 XGBoost RCA + NetworkX Causal Reasoning Pipeline

```
Anomalous Telemetry & Severity Flags
    │
    ▼
┌────────────────────────────────────────────────────────┐
│    Supervised XGBoost Classifier (`xgboost_rca.pkl`)   │
│             Objective: multi:softprob (8 classes)      │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
Class Probabilities: [DATABASE: 91.2%, TRAFFIC_SPIKE: 4.1%, NETWORK: 2.8%, ...]
Primary Cause Identified: `DATABASE`
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│     NetworkX Causal Dependency Graph (`nx.DiGraph`)    │
└───────────────────────────┬────────────────────────────┘
                            │
                    DAG Traversal & Pathing:
                            │
                       RESULT DAY
                            │
                            ▼
                      TRAFFIC SPIKE
                            │
                            ▼
                        API LOAD
                       /        \
                      ▼          ▼
                  DB POOL 🔴    CPU (38% nominal)
                      │
                      ▼
                  QUERY WAIT
                      │
                      ▼
                   LATENCY
                      │
                      ▼
                     503
                            │
                            ▼
Active Causal Propagation Chain Isolated:
`RESULT_DAY → TRAFFIC_SPIKE → API_LOAD → DB_POOL → QUERY_WAIT → LATENCY → ERR_503`
```

---

### Diagram 6: M5 PyTorch Tactical Policy + M6 Deterministic Safety Layer

```
Input State Vector (M1 Derived + M2 CPI + M3 Anomaly Score + M4 RCA Probabilities)
    │
    ▼
┌────────────────────────────────────────────────────────┐
│  M5 PyTorch Deep Policy MLP (`action_mlp_policy.pt`)   │
│  Linear(16 -> 64) -> ReLU -> Linear(64 -> 32) -> Linear(32 -> 11) Softmax │
└───────────────────────────┬────────────────────────────┘
                            │
Candidate Action: `ENABLE_WAITING_ROOM` (Confidence: 97.2%)
Blast Radius: `MEDIUM`
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│               M6 Deterministic Safety Layer            │
└───────────────────────────┬────────────────────────────┘
                            │
 1. Confidence Gate: Is confidence >= 80%? ─────────────► [YES: 97.2%]
 2. Flapping Cooldown: Last identical action > 300s? ────► [YES: No recent action]
 3. Token Bucket Ingress: Rate limiter within bounds? ──► [YES: Tokens available]
 4. Blast Radius Check: High blast radius? ──────────────► [NO: Medium - Auto-Approved]
 5. Replica Boundary: Pod replicas within [2, 24]? ──────► [YES: Preserved]
                            │
                            ▼
            Validated Action Execution Permitted:
                    `PASS (SAFE TO ACTUATE)`
```

---

### Diagram 7: Complete Autonomous Closed-Loop Lifecycle

```
┌───────────────────────────────────────────────────────────────────────────────┐
│                               PHASE 1: TRAFFIC                                │
│  Result-day exam surge generated by Locust / Live Users (12,481 VUs, 4,820 RPS)│
└──────────────────────────────────────┬────────────────────────────────────────┘
                                       │
                                       ▼
┌───────────────────────────────────────────────────────────────────────────────┐
│                               PHASE 2: TELEMETRY                              │
│  M1 collects p95 latency = 2.41s, DB pool = 96%, HTTP 5xx = 5.8%              │
└──────────────────────────────────────┬────────────────────────────────────────┘
                                       │
                                       ▼
┌───────────────────────────────────────────────────────────────────────────────┐
│                          PHASE 3: PREDICTIVE INFERENCE                        │
│  M2 forecasts capacity breach in ~7 min | M3 detects anomaly score = 0.94     │
└──────────────────────────────────────┬────────────────────────────────────────┘
                                       │
                                       ▼
┌───────────────────────────────────────────────────────────────────────────────┐
│                        PHASE 4: ROOT CAUSE & POLICY                           │
│  M4 isolates DB Pool exhaustion (91.2%) | M5 recommends ENABLE_WAITING_ROOM   │
└──────────────────────────────────────┬────────────────────────────────────────┘
                                       │
                                       ▼
┌───────────────────────────────────────────────────────────────────────────────┐
│                        PHASE 5: DETERMINISTIC SAFETY                          │
│  M6 validates confidence (97.2% > 80%), enforces cooldown, approves action    │
└──────────────────────────────────────┬────────────────────────────────────────┘
                                       │
                                       ▼
┌───────────────────────────────────────────────────────────────────────────────┐
│                         PHASE 6: CLOSED-LOOP ACTUATION                        │
│  M7 executes ENABLE_WAITING_ROOM on SDK middleware                            │
│  Trajectory: PRE-ACTION ──► CRITICAL ──► ACTUATING ──► STABILIZING ──► NOMINAL│
└──────────────────────────────────────┬────────────────────────────────────────┘
                                       │
                                       ▼
┌───────────────────────────────────────────────────────────────────────────────┐
│                         PHASE 7: SYSTEM STABILIZATION                         │
│  DB Pool: 96% ──► 71% (-26% relief) | Latency: 2.41s ──► 1.62s (-32.8% relief)│
│  SLA restored | Status: RECOVERY VERIFIED                                     │
└──────────────────────────────────────┬────────────────────────────────────────┘
                                       │
                                       ▼
┌───────────────────────────────────────────────────────────────────────────────┐
│                           PHASE 8: FEEDBACK / NEXT CYCLE                      │
│  Cycle #043 initiates, ingests post-relief telemetry, maintains nominal state │
└───────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Public Deployment & Operational Boundary Specification

- **Frontend Target (`here.now`)**:
  - Serves static assets, CSS, SVG canvas graphics, and interactive command center.
  - Decoupled from backend origin via dynamic configuration (`window.PORTALPULSE_BACKEND_URL`, `<meta name="portalpulse-backend-url">`, or localStorage).
  - Connects to backend endpoints over HTTPS and Server-Sent Events (SSE).
- **Backend Target (Antideploy)**:
  - FastAPI server exposed at `0.0.0.0:${PORT:-8000}`.
  - Houses all 4 machine learning models, NetworkX DAG, safety token buckets, and SSE broadcaster.
- **Nirantar Invariant**:
  - Nirantar code and database remain strictly read-only and unmodified. PortalPulse communicates exclusively through external telemetry connectors and non-invasive middleware bridges.
