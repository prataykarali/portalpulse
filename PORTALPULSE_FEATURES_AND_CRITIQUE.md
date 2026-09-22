# PortalPulse: Exhaustive Feature Inventory, Architectural Analysis & Critical Audit

> **System Classification**: Autonomous SRE, Predictive Telemetry Intelligence & Closed-Loop Capacity Protection Platform for High-Concurrency Portals.  
> **Evaluation Scope**: Complete repository audit spanning Frontend Shell, Demo Portals, Streamlit Dashboards, FastAPI Gateway, Control Plane, Connectors, Micro-Modules (M1–M9), SDK, Data Pipelines, Academic Evolution (Weeks 1–5), Security Infrastructure, and CLI Tooling.  
> **Auditor Mode**: Highly Technical SRE & Software Architect / Critical Codebase Reviewer.

---

## Table of Contents

1. [Executive Summary & System Anatomy](#1-executive-summary--system-anatomy)
2. [Frontend Web Application (`website/`) & Reference Portals](#2-frontend-web-application-website--reference-portals)
   - [2.1 Global Application Shell, Navigation & Interactive Mascots](#21-global-application-shell-navigation--interactive-mascots)
   - [2.2 Page 1: Overview / Autonomous Command Center](#22-page-1-overview--autonomous-command-center)
   - [2.3 Page 2: Portals Fleet Directory](#23-page-2-portals-fleet-directory)
   - [2.4 Page 3: Portal Deep Dive & Architectural Topology](#24-page-3-portal-deep-dive--architectural-topology)
   - [2.5 Page 4: Monitoring APM & Multi-Series Telemetry](#25-page-4-monitoring-apm--multi-series-telemetry)
   - [2.6 Page 5: Incidents Master-Detail & Causal RCA](#26-page-5-incidents-master-detail--causal-rca)
   - [2.7 Page 6: Action Center & Governance Execution](#27-page-6-action-center--governance-execution)
   - [2.8 Page 7: Integrations & 4-Step Pluggable Handshake Wizard](#28-page-7-integrations--4-step-pluggable-handshake-wizard)
   - [2.9 Page 8: Settings, Autonomy Policies & Access Control](#29-page-8-settings-autonomy-policies--access-control)
   - [2.10 Reference Portals & Integrated Sub-Applications](#210-reference-portals--integrated-sub-applications)
3. [Streamlit Production & Prototype Dashboards (`dashboard/` & `week*`)](#3-streamlit-production--prototype-dashboards-dashboard--week)
   - [3.1 Cryptographic Persona Gateway (Student, Faculty, Master Admin)](#31-cryptographic-persona-gateway-student-faculty-master-admin)
   - [3.2 Student Persona Workspace (Academic Results & Redirect Risk)](#32-student-persona-workspace-academic-results--redirect-risk)
   - [3.3 Faculty Studio (Grade Entry & Real-Time Cache Invalidation)](#33-faculty-studio-grade-entry--real-time-cache-invalidation)
   - [3.4 Master Admin Control Tower (13 Dedicated Inspection Views)](#34-master-admin-control-tower-13-dedicated-inspection-views)
   - [3.5 Academic Week Prototypes (Week 1 MLP & Week 2 Simulator)](#35-academic-week-prototypes-week-1-mlp--week-2-simulator)
4. [Backend Control Plane, Connectors & Multi-Portal Gateway](#4-backend-control-plane-connectors--multi-portal-gateway)
   - [4.1 FastAPI Gateway Architecture & Lifespan Telemetry Streamer](#41-fastapi-gateway-architecture--lifespan-telemetry-streamer)
   - [4.2 Control Plane Registry, Ring Buffer & Connection Lifecycle](#42-control-plane-registry-ring-buffer--connection-lifecycle)
   - [4.3 Dynamic NetworkX Topological Dependency Engine](#43-dynamic-networkx-topological-dependency-engine)
   - [4.4 Capability Discovery & The Action Masker Engine](#44-capability-discovery--the-action-masker-engine)
   - [4.5 Statistical Normal Operating Baseline Engine](#45-statistical-normal-operating-baseline-engine)
   - [4.6 Pluggable Reference Connectors (Nirantar, College, E-Commerce, Gov)](#46-pluggable-reference-connectors-nirantar-college-e-commerce-gov)
5. [The 10 Autonomous SRE Intelligence Micro-Modules (M1–M9)](#5-the-10-autonomous-sre-intelligence-micro-modules-m1m9)
   - [5.1 M1: APM Telemetry Ingestion & Portal Simulator](#51-m1-apm-telemetry-ingestion--portal-simulator)
   - [5.2 M2: Multi-Horizon Predictive Forecaster (XGBoost / LightGBM / MLP)](#52-m2-multi-horizon-predictive-forecaster-xgboost--lightgbm--mlp)
   - [5.3 M3: Unsupervised Outlier Detection (Isolation Forest)](#53-m3-unsupervised-outlier-detection-isolation-forest)
   - [5.4 M4: Root Cause Analysis (XGBoost 8-Class Classifier & Causal DAG)](#54-m4-root-cause-analysis-xgboost-8-class-classifier--causal-dag)
   - [5.5 M5: Tactical Action Intelligence Policy Network (PyTorch RTX 2050 CUDA)](#55-m5-tactical-action-intelligence-policy-network-pytorch-rtx-2050-cuda)
   - [5.6 M5.5: AI SRE Operations Copilot & RAG Knowledge Base](#56-m55-ai-sre-operations-copilot--rag-knowledge-base)
   - [5.7 M6: Deterministic Safety Layer (Zero-ML Guardrails & Token Bucket)](#57-m6-deterministic-safety-layer-zero-ml-guardrails--token-bucket)
   - [5.8 M7: Closed-Loop Actuator & Feedback Stabilization Trajectory](#58-m7-closed-loop-actuator--feedback-stabilization-trajectory)
   - [5.9 M8: Chaos Engineering Lab & Analytical M/M/c Knee Curvature](#59-m8-chaos-engineering-lab--analytical-mmc-knee-curvature)
   - [5.10 M9: MLOps Drift Governance (KS-Test, PSI & Model Registry)](#510-m9-mlops-drift-governance-ks-test-psi--model-registry)
6. [PortalPulse Universal Connector SDK (`portalpulse_sdk`)](#6-portalpulse-universal-connector-sdk-portalpulse_sdk)
   - [6.1 ASGI/WSGI Active Session & In-Flight Concurrency Middleware](#61-asgiwsgi-active-session--in-flight-concurrency-middleware)
   - [6.2 Client Agent Daemon & Heartbeat Loop](#62-client-agent-daemon--heartbeat-loop)
   - [6.3 Hardware Discovery & Linux cgroup v1/v2 Quota Detection](#63-hardware-discovery--linux-cgroup-v1v2-quota-detection)
   - [6.4 Out-of-Process Capacity Benchmark Worker (`load_worker.py`)](#64-out-of-process-capacity-benchmark-worker-load_workerpy)
7. [Database Architecture, Hybrid Redis Caching & Quantum Security](#7-database-architecture-hybrid-redis-caching--quantum-security)
   - [7.1 SQLite WAL Schema & Query Audit Trail](#71-sqlite-wal-schema--query-audit-trail)
   - [7.2 Hybrid Redis Caching Engine with In-Memory LRU Fallback](#72-hybrid-redis-caching-engine-with-in-memory-lru-fallback)
   - [7.3 Cryptographic Access Tokens & Constant-Time Verification](#73-cryptographic-access-tokens--constant-time-verification)
8. [Data Science, Datasets & Academic Syllabus Mapping](#8-data-science-datasets--academic-syllabus-mapping)
   - [8.1 Master Telemetry Dataset (`Module1_Data`) & Split Manifest](#81-master-telemetry-dataset-module1_data--split-manifest)
   - [8.2 5-Model Empirical Evaluation & Benchmarks](#82-5-model-empirical-evaluation--benchmarks)
   - [8.3 Syllabus Mapping (Weeks 1 through 5)](#83-syllabus-mapping-weeks-1-through-5)
9. [DevOps, Automation CLI, Testing & CI/CD](#9-devops-automation-cli-testing--cicd)
10. [Comprehensive Critical Review: Strengths, Gaps, Bugs & Production Vulnerabilities](#10-comprehensive-critical-review-strengths-gaps-bugs--production-vulnerabilities)

---

## 1. Executive Summary & System Anatomy

**PortalPulse** is an enterprise-grade autonomous Site Reliability Engineering (SRE) and traffic capacity protection platform tailored for mission-critical web portals (academic ERPs, national railway booking engines, flash-sale retail stores, and digital government gateways). 

### Core Architectural Philosophy
1. **Coupled Telemetry Observation**: Simultaneously observes three distinct traffic dimensions:
   - **Active User Sessions**: Human clients actively engaged within a 30-second sliding window.
   - **Arrival Throughput (RPS)**: Ingress HTTP transaction rate.
   - **In-Flight Concurrency ($L$)**: Requests executing concurrently inside server memory ($L = \lambda \cdot W$).
2. **Predictive Horizon Forecasting**: Forecasts safe capacity, CPU, and database connection starvation 15 minutes before latency spikes occur.
3. **Deterministic Zero-ML Safety**: Separates predictive machine learning (XGBoost, Isolation Forest, PyTorch MLP) from execution actuation. No ML model directly invokes production infrastructure commands; every recommendation passes through deterministic capability masking, confidence thresholds ($\ge 80\%$), flapping cooldowns (300s), and human-in-the-loop (HITL) approval gates.
4. **Universal Pluggable Connector SDK**: Operates via a standardized contract (`BasePortalConnector`), eliminating the need for application-specific code inside the PortalPulse core.

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                           PORTALPULSE CONTROL TOWER                              │
├─────────────────────────────────────────┬────────────────────────────────────────┤
│   FRONTEND INTERFACE & DASHBOARDS       │   BACKEND GATEWAY & CONTROL PLANE      │
│   • Dark Cyber Web Shell (Vanilla JS)   │   • FastAPI Unified Gateway (:8000)    │
│   • Production Streamlit Console (:8501)│   • PortalRegistry (In-Memory + WAL)   │
│   • 3 Reference Demo Portals            │   • ActionMasker (Capability Filtering)│
│   • Live Mounted Nirantar App           │   • Dynamic NetworkX Causal DAG Engine │
├─────────────────────────────────────────┴────────────────────────────────────────┤
│                         THE 10 AUTONOMOUS SRE MODULES                            │
│ ┌──────────────────────┬──────────────────────┬────────────────────────────────┐ │
│ │ Ingestion & Sensing  │ Diagnostic & Policy  │ Execution & Governance         │ │
│ ├──────────────────────┼──────────────────────┼────────────────────────────────┤ │
│ │ M1: APM Telemetry    │ M3: Isolation Forest │ M6: Deterministic Safety Layer │ │
│ │ M2: XGBoost Forecast │ M4: XGBoost RCA + DAG│ M7: Closed-Loop Actuator       │ │
│ │                      │ M5: Deep PyTorch MLP │ M8: Chaos Engineering Lab      │ │
│ │                      │ M5.5: Copilot RAG    │ M9: MLOps Drift & Registry     │ │
│ └──────────────────────┴──────────────────────┴────────────────────────────────┘ │
├──────────────────────────────────────────────────────────────────────────────────┤
│             PORTALPULSE UNIVERSAL SDK & OUT-OF-PROCESS BENCHMARK                 │
│ • ActiveSessionTracker (30s window)        • Linux cgroup v1/v2 Envelope Detector│
│ • TokenBucket Rate Limiter (5000 tokens)   • load_worker.py (Async Virtual Users)│
├──────────────────────────────────────────────────────────────────────────────────┤
│                 STORAGE, PERSISTENCE & CRYPTOGRAPHIC ACCESS                      │
│ • SQLite WAL Persistence (students, grades)• Redis Hybrid Cache (< 1ms hits)     │
│ • HMAC-SHA256 Role Access Tokens (RBAC)    • PostgreSQL Enterprise Migration Path│
└──────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Frontend Web Application (`website/`) & Reference Portals

The primary administrative console is housed in `website/` (served at `http://localhost:8000/app` or `http://localhost:8000/`), written in pure modern JavaScript (`app.js`, 1,141 lines), semantic HTML5 (`index.html`, 1,564 lines), and responsive CSS3 (`style.css`, 1,842 lines).

### 2.1 Global Application Shell, Navigation & Interactive Mascots

#### Topbar Controls
- **Global Search Bar**: Search input with keyboard shortcut `/` placeholder, searching across portals, documentation, and connectors.
- **Theme Switcher**: Instant dark/light mode toggle (`☀️` / `🌙`), dynamically swapping CSS custom properties (`--bg-primary`, `--card-bg`, `--text-primary`, `--border-subtle`).
- **Incident Notification Bell**: Displays an animated unread badge dot (`1`), linking directly to `#/app/incidents`.
- **User Profile Pill**: Displays current authenticated operator avatar (`boy_happy.png`), user name (`Pratay`), and badge (`Administrator ▾`), linking to Settings.

#### Sidebar Navigation & Dynamic Mascots
- **Brand Identity**: Animated pulse SVG icon with title "PortalPulse" and subtitle "Every Portal. Always On." Clicking navigates to `#/app/overview`.
- **Sidebar Menu**: 7 navigational buttons with SVG icons and active state indicators:
  1. `Overview` (`#/app/overview`)
  2. `Portals` (`#/app/portals`)
  3. `Monitoring` (`#/app/monitoring`)
  4. `Incidents` (`#/app/incidents`)
  5. `Actions` (`#/app/actions`)
  6. `Integrations` (`#/app/integrations`)
  7. `Settings` (`#/app/settings`)
- **3D Mascot & Dynamic Chalk Quote Box**:
  - Displays a waving 3D robot (`robot_sidebar_nobg.png`). Clicking triggers a pose change (`robot_celebrating`).
  - Handwritten chalk quote bubble dynamically updates based on the current page:
    - *Overview*: `"Good systems make brighter tomorrows! 💙"`
    - *Portals*: `"Observing, Predicting, Improving Together 💙"`
    - *Monitoring*: `"Real-time insights. Real impact. 💙"`
    - *Incidents*: `"Turn Incidents into a Stronger Tomorrow. 💜"`
    - *Actions*: `"Smarter Actions, Happier People 💜"`
    - *Integrations*: `"Plug, Integrate, Monitor, Grow 💜"`
    - *Settings*: `"Small actions. Big uptime. 💜"`
- **Need Help Card**: Quick support card with "View Docs →" button.
- **Floating Interactive Emotion Dock**:
  - Collapsible bottom dock (`#emotionDock`) allowing the operator to manually preview 13 custom character emotions:
    - **Boy Poses (6)**: Happy (`boy_happy`), Thinking (`boy_thinking`), Thumbs Up (`boy_winking`), Working (`boy_working`), Excited (`boy_excited`), Coffee Break (`boy_mug`).
    - **Robot Poses (7)**: Wave (`robot_happy`), Question/Think (`robot_thinking`), Excited (`robot_excited`), Explain (`robot_explaining`), Typing (`robot_typing`), Fly (`robot_flying`), Star Celebrating (`robot_celebrating`).

---

### 2.2 Page 1: Overview / Autonomous Command Center (`#page-overview`)

Designed as a mission-control command center matching high-concurrency SRE operational demands:

1. **Header & Telemetry Mode Toggle**:
   - Operator greeting with live duo artwork (`overview_hero_duo.jpg`).
   - **Mode Switch**:
     - `Real Baseline (Live)`: Displays actual idle operator telemetry (1 session, 0.2 RPS, ~1.5ms latency).
     - `Benchmark Test (Simulated)`: Toggles connectors into high-concurrency stress test mode (~4,821 sessions, 812 RPS, 168ms latency). Calls `POST /api/v1/portals/telemetry/mode?simulation={true|false}`.
2. **4 Top Command Stat Cards**:
   - `Connected Portals`: Value `4` (Delta: `↑ +2`).
   - `Active Sessions / Users`: Value `67.0K` (Delta: `↑ 14%`).
   - `Average SLA Latency`: Value `32 ms` (Delta: `↓ 8%`).
   - `System Availability`: Value `99.98%` (Delta: `↑ 0.02%`).
3. **Discovered Physical Envelope & Resource Limits**:
   - Displays real discovered machine capacity discovered via `detect_cgroup_limits()`:
     - Host CPU Cores (`16 Cores Physical`)
     - Cgroup CPU Quota (`Uncapped (Host)`)
     - System Memory (`15.5 GB RAM`)
     - Worker Allocation (`8 Workers / 8 Pods`)
     - Database Pool (`150 Pool / 200 Max`)
     - Storage Volume (`146.6 GB Disk`)
4. **Empirical Measured Capacity Profile**:
   - Displays real load-test findings:
     - Sustainable Under SLA: `356.1 RPS`
     - Degradation Knee: `419 RPS (2500 VUs)`
     - Saturation Ceiling: `565.7 RPS`
     - Safe Active Sessions: `3,750 Sessions`
     - Primary Constrained Tier: `WORKER_CPU_SATURATION`
5. **Controlled Capacity Benchmark & Closed-Loop AIOps Console**:
   - Interactive load generator controls:
     - Portal target selector dropdown (`nirantar`, `college_portal`, `ecommerce`, `gov_portal`).
     - "⚡ Run Capacity Benchmark" and "⏹ Stop Benchmark" buttons calling `POST /api/v1/simulation/capacity-benchmark/start`.
     - Live progress bar, VU ramp-up meter (500 → 5,000 VUs), step status badge (`● Healthy`, `▲ Knee Warning`, `■ Saturated`), and live latency chart with SLA boundary indicator line.
6. **Connected Portals Fleet Quick Status**:
   - Real-time status cards for Nirantar (0.24 req/s), College Portal (0.12 req/s), E-Commerce (0.18 req/s), and Gov Services (0.08 req/s) with instant health badges.
7. **Real-Time Forecasting Chart**:
   - Multi-horizon predictive SVG area chart showing past 30 minutes and 15-minute lookahead forecasting with shaded 95% confidence intervals.
8. **Recent Incidents Feed & Autonomous Actions Feed**:
   - Displays active anomalies with severity badges and action cards with interactive "Review" governance buttons.
9. **Bottom Call-to-Action Banner**:
   - Atmospheric train banner (`bottom_train_night.jpg`) with "+ Connect Portal" quick launch link.

---

### 2.3 Page 2: Portals Fleet Directory (`#page-portals`)

A centralized catalog of all connected portal infrastructures:
- **Filter Tabs**: All (4), Healthy (2), Warning (1), Critical (1).
- **Portal Cards Grid**:
  1. **Nirantar National Railway ERP**: Railway ERP, status `Healthy 🟢`, 4,821 active users, 812 RPS, 340ms latency, 0.4% errors.
  2. **State University Exam Results Portal**: Education, status `Warning 🟡`, 1,240 active users, 42 RPS, 820ms latency, 1.2% errors.
  3. **SuperDeal E-Commerce Storefront**: Retail, status `Critical 🔴`, 8,420 active users, 1,240 RPS, 1,420ms latency, 2.8% errors.
  4. **National Digital Governance Gateway**: Civic Infrastructure, status `Healthy 🟢`, 2,150 active users, 95 RPS, 120ms latency, 0.1% errors.
- **Card Controls**:
  - "Inspect Deep Dive" button opening `#/app/portal-detail?portal={id}`.
  - External link button opening the live portal in a new tab.
  - SVG sparkline reflecting historical arrival throughput.

---

### 2.4 Page 3: Portal Deep Dive & Architectural Topology (`#page-portal-detail`)

Detailed operational breakdown for any specific portal:
1. **Header**: Portal branding, category, status pill, external launch link, return button.
2. **KPI Metrics Grid**: 4 stat cards with sparklines (Active Users, Requests/sec, Avg Latency, Error Rate).
3. **Traffic & Usage Chart**: Time-window toggles (1h, 6h, 24h) with SVG linear gradient area fill.
4. **Hardware Saturation Meters**: CPU usage gauge, RAM usage gauge, Database Connection Pool bar, Disk I/O bar.
5. **Topological Service Dependency Graph**:
   - Renders a dynamic NetworkX Directed Acyclic Graph (DAG) visualizing architectural tiers:
     - `Client / Ingress` → `CDN Edge (Cloudflare)` → `API Gateway` → `Backend Workers` → `PostgreSQL / MySQL` + `Redis Cache`.
     - Nodes highlight real-time localized stress (green/amber/red).
6. **Predictive Insights Panel**:
   - Model consensus prediction, time-to-saturation estimation, and safe capacity recommendation.
7. **Infrastructure Capabilities Matrix**:
   - Interactive badges displaying enabled (`✓`) vs disabled (`✕`) capabilities:
     - Horizontal Scaling (`✓`)
     - Caching (`✓` or `✕` depending on portal)
     - Request Queue (`✓`)
     - Rate Limiting (`✓`)
     - Database Read Replica (`✓` or `✕`)
     - Feature Flags (`✓` or `✕`)
8. **On-Demand Capacity Benchmark Runner**: Dedicated per-portal benchmark trigger.

---

### 2.5 Page 4: Monitoring APM & Multi-Series Telemetry (`#page-monitoring`)

Enterprise APM observability view:
- **Portal Selection Filter**: Tabs for "All Portals", "Nirantar", "College Portal", "E-Commerce", "Gov Services".
- **4 Aggregate KPI Cards**: Requests/sec, P95 Latency, CPU Usage, Error Rate.
- **4 Dedicated Multi-Series Telemetry Charts**:
  1. *Throughput (RPS)*: Ingress requests per second vs served throughput.
  2. *Latency Distribution*: P50, P95, and P99 latency percentiles plotted against the 800ms SLA threshold.
  3. *Resource Saturation*: CPU % vs RAM % plotted against the 85% safety boundary.
  4. *Error Rate & HTTP Codes*: 4xx client errors vs 5xx server exceptions.
- **Background Telemetry Polling**: Asynchronous polling every 3.5 seconds refreshing values without page flicker.

---

### 2.6 Page 5: Incidents Master-Detail & Causal RCA (`#page-incidents`)

Incident triage and root-cause analysis console:
- **Filter Tabs**: All (3), Active (1), Resolved (2).
- **Incident Cards Stack**:
  1. `#PP-1042 Database Latency Spike` (E-Commerce, Critical, 12,430 impacted users, 3,420ms latency).
  2. `#PP-1041 High Memory Usage` (College Portal, Warning, 8,120 impacted users, 1,220ms latency).
  3. `#PP-1040 Traffic Surge Detected` (Nirantar, Info, 34,347 impacted users, 340ms latency).
- **Deep Investigation Drawer / Detail Pane**:
  - Incident title, severity pill, target portal, detection timestamp.
  - Metric breakdown: Impacted Users, Error Rate, Peak Latency.
  - **AI Causal Analysis (Module 4)**: Plain English explanation of the failure cascade (e.g. *"Database latency has increased by 3.1x due to a sudden rise in active connections. This is causing a cascading increase in API response time."*).
  - **Recommended Mitigation Action**: Proposed action (e.g., `Add Read Replica`), estimated impact (`-60% latency offload`), and "Take Action" button triggering the Review Modal.
  - **Collaboration Bar**: Text input to assign team members or add notes, and "Mark as Resolved" button.

---

### 2.7 Page 6: Action Center & Governance Execution (`#page-actions`)

The execution and audit trail interface for automated and operator mitigations:
- **Status Tabs**: Recommended (3), In Progress (1), Completed (12).
- **Proposed Action Cards**:
  - Action name, blast radius badge (`LOW`, `MEDIUM`, `HIGH`), target portal, detailed description, expected outcome, and "Approve & Execute" button.
- **Action Masker Governance Rationale**:
  - Explains why certain raw model recommendations were masked out (e.g., explaining that `DIVERT_READS_TO_REPLICA` was masked on College Portal because it lacks database replicas, diverting instead to `ENABLE_WAITING_ROOM`).
- **Completed Actions Audit Trail**:
  - Immutable execution history table with timestamp, action type, executor ID, and observed delta.

---

### 2.8 Page 7: Integrations & 4-Step Pluggable Handshake Wizard (`#page-integrations`)

The onboarding center for integrating arbitrary web portals into PortalPulse:

```
[1. Choose Framework] ──> [2. Get API Key] ──> [3. Integrate SDK] ──> [4. Verify Handshake]
```

- **Step 1: Choose Framework**: Selectable tech stacks: FastAPI (Python), Django (Python), Flask (Python), Express (Node.js), Go (Gin/Fiber).
- **Step 2: Provision API Key**:
  - Generates secure long-lived connector keys (`pp_live_...`).
  - Copy API Key button and "Regenerate Key" button calling `POST /api/v1/portals/keys/provision`.
- **Step 3: Integrate SDK**:
  - Dynamically generated copy-paste code snippet showing how to import `PortalPulseAgent`, declare capabilities, and attach `PortalPulseSessionMiddleware`.
- **Step 4: Verify Handshake & Telemetry**:
  - Interactive "Run Handshake Test" button verifying 4 verification stages:
    1. Connector Authentication Handshake
    2. Capabilities Discovery Verification
    3. Topological Dependency Registration
    4. First Telemetry Frame Ingestion
- **Connectors Registry**: List of pre-configured reference connectors.
- **Webhook & Prometheus Export**: Endpoints for Prometheus scraping (`/metrics`) and PagerDuty/Slack webhooks.

---

### 2.9 Page 8: Settings, Autonomy Policies & Access Control (`#page-settings`)

Platform configuration and governance controls:
- **Profile Management**: Displays current operator (`Pratay`), email, and clearance tier.
- **Appearance**: Dark vs Light theme switcher.
- **Autonomy Operating Mode Dropdown**:
  1. `Assisted (Human Operator Review Required)`: All actions require manual approval.
  2. `Autonomous (Safe Guardrails Auto-Approve)`: Low-blast-radius actions auto-execute; high-blast-radius actions queue for HITL.
  3. `Dry Run (Shadow Policy Only)`: Policy network evaluates without executing infrastructure mutations.
- **Notification & SLA Thresholds**: Sliders for latency alert thresholds (default 800ms) and CPU saturation thresholds (default 85%).
- **Quantum Access Key Verification**: Input field to validate 256-bit symmetric entropy keys.

---

### 2.10 Reference Portals & Integrated Sub-Applications

PortalPulse includes 4 distinct target portals demonstrating heterogeneous architectures:
1. **Nirantar National Railway ERP (`/portals/nirantar`)**:
   - Real compiled production web application (React + Vite, loaded from `/portals/nirantar` or external URL).
   - High-concurrency train booking, PNR status lookup, and Tatkal rush simulation.
2. **State University Exam Results Portal (`website/portals/college/index.html`)**:
   - Monolithic legacy architecture (PHP + MySQL).
   - Student roll number verification, semester exam grade lookup, and provisional marksheet download.
   - Connected banner displaying PortalPulse connection status.
3. **SuperDeal E-Commerce Storefront (`website/portals/ecommerce/index.html`)**:
   - Modern microservices retail portal.
   - Flash deal product listings, shopping cart counter, instant checkout button, and checkout latency guard banner.
4. **National Digital Governance Gateway (`website/portals/gov/index.html`)**:
   - Digital public infrastructure portal.
   - Citizen services: Aadhaar e-KYC verification, civil birth/caste certificates, public grievance redressal.

---

## 3. Streamlit Production & Prototype Dashboards (`dashboard/` & `week*`)

The repository includes a production Streamlit application (`dashboard/app.py`, 2,062 lines) running on port `8501`, as well as historical prototype dashboards from Weeks 1 and 2.

### 3.1 Cryptographic Persona Gateway (Student, Faculty, Master Admin)

Access to `dashboard/app.py` is protected by a cryptographic Persona Gateway using constant-time comparison (`hmac.compare_digest`):

| Persona | Cryptographic Token | Scoped Capabilities |
|---|---|---|
| **🎓 Student** | `STU-SEC-3B8A7F1C9E20` *(Legacy: `STU-QKEY-3B8A7F1C9E20`)* | Enrolled course marks, CGPA, cold vs cached query latency benchmark, session health & redirect risk. |
| **👨‍🏫 Faculty** | `FAC-SEC-5E6C1D94A8B2` *(Legacy: `FAC-QKEY-5E6C1D94A8B2`)* | Departmental course roster, interactive grade entry form, real-time cache invalidation. |
| **🛡️ Master Admin** | `ADM-SEC-7F9A2B81C3D4` *(Legacy: `ADM-QKEY-7F9A2B81C3D4`)* | Global Control Tower, live traffic simulator, SQLite WAL inspector, Redis caching benchmark, defense modes. |

---

### 3.2 Student Persona Workspace (Academic Results & Redirect Risk)

Accessible exclusively to the Student persona:
1. **Academic Results Portal (`My Student Portal`)**:
   - Displays student profile: enrollment number, name, department, semester, and current CGPA.
   - Course grades table: Subject code, subject name, credit points, grade letter, and grade point.
   - **Real-Time Database Latency Meter**: Measures actual SQLite execution time vs Redis cache hits (< 1ms).
2. **Session Health & Redirect Risk (`Session Health & Redirect Risk`)**:
   - Calculates mathematical probability of session shedding:
     $$\text{Risk} = \min\left(100.0, \left(\frac{\text{Current Users}}{\text{Safe Capacity}}\right)^{2.5} \times 15.0\right)$$
   - Displays admission odds, queue state, and recommendations for the student.

---

### 3.3 Faculty Studio (Grade Entry & Real-Time Cache Invalidation)

Accessible to Faculty and Master Admin:
- **Departmental Student Roster**: Filter students by department (CSE, ECE, EE, ME) and semester.
- **Grade Entry & Modification Form**: Select student enrollment number, course code, grade point, and letter grade.
- **Real-Time Cache Invalidation**: When a faculty member updates a grade, `dashboard/db.py` executes an atomic SQLite update and simultaneously invalidates the corresponding Redis cache key (`student_results:{enrollment_no}`), ensuring the student immediately sees updated results on their next query.

---

### 3.4 Master Admin Control Tower (13 Dedicated Inspection Views)

The Master Admin has access to 13 comprehensive views:

```
[🗼 Control Tower]    [🏠 Dashboard]       [🚀 Simulator]     [🧪 Custom Stress Lab]
[👥 All Accounts]     [🎓 Student Portal]  [👨‍🏫 Faculty Studio][📊 Telemetry]
[⚙️ Models (ML)]      [🏆 Benchmarks (ML)] [📈 Insights]      [⚡ Architecture]
[📄 Reports]
```

1. **🗼 Control Tower**:
   - Model consensus predictions across 5 architectures.
   - Uncertainty estimation bounds.
   - Prescriptive capacity advisor (automated recommendations for pod count and DB connection pool sizing).
   - Real-time closed-loop control status (🟢 SAFE, 🟡 PREPARE, 🔴 CRITICAL).
2. **🏠 Dashboard**:
   - High-level executive overview with SLA gauges (800ms latency threshold, 85% CPU threshold).
3. **🚀 Simulator**:
   - Interactive live scenario runner:
     - 5 Pre-configured Scenarios: *Result Declaration Rush*, *Regular Academic Day*, *Exam Fee Registration*, *Course Registration Rush*, *Off-Peak Night*.
     - Sliders for Concurrent Users ($200 \to 13,000$), Pod Replicas ($1 \to 16$), DB Connection Pool ($20 \to 250$), Cache Hit Ratio ($0\% \to 95\%$).
     - Defense toggles: Virtual Waiting Room, Graceful Degraded Mode.
     - Fault injector: Database Deadlock, Slow Query Contention, Memory Leak, Packet Drop.
4. **🧪 Custom Stress Lab**:
   - Multi-point concurrency sweep engine.
   - Automatically sweeps user load from 1,000 to 12,000 users in increments, evaluates system response, and detects the exact analytical saturation knee.
5. **👥 All Accounts Directory**:
   - Searchable directory of all student and faculty records in the SQLite database.
6. **🎓 Student Portal & DB**:
   - Admin view of student records with direct CRUD functionality (add student, delete student, view grades).
   - Built-in 60-query SQLite vs Redis benchmark runner.
7. **👨‍🏫 Faculty Studio**:
   - Administrative view of the faculty grade publishing console.
8. **📊 Telemetry**:
   - Detailed time-series inspection of CPU, memory, latency, RPS, and database lock waits.
9. **⚙️ Models (ML)**:
   - Deep inspection of trained model weights, feature importances, hyperparameters, and inference latency benchmarks.
10. **🏆 Benchmarks (ML)**:
    - Side-by-side empirical benchmark comparison of all 5 evaluated architectures (XGBoost, LightGBM, PyTorch MLP, Random Forest, Ridge).
11. **📈 Insights**:
    - Automated heuristics and SLA violation risk assessments.
12. **⚡ Architecture & Migration**:
    - Deep-dive into SQLite WAL mode, Redis hybrid caching topology, and PostgreSQL enterprise migration roadmap.
13. **📄 Reports**:
    - Telemetry export engine supporting CSV and JSON downloads.

---

### 3.5 Academic Week Prototypes (Week 1 MLP & Week 2 Simulator)

- **Week 1 Prototype (`week1/team3_dashboard/app_week1.py`)**:
  - Baseline PyTorch MLP predicting CPU usage, Latency, and Safe Capacity from telemetry with ReLU activations and Adam optimizer.
- **Week 2 Prototype (`week2/team3_dashboard/app.py`)**:
  - 5-Model benchmark evaluation dashboard with coupled telemetry synthesizer and live decision engine.

---

## 4. Backend Control Plane, Connectors & Multi-Portal Gateway

The core backend service is a high-performance asynchronous FastAPI application (`backend/app.py`, 187 lines) running on port `8000`.

### 4.1 FastAPI Gateway Architecture & Lifespan Telemetry Streamer

- **Unified Lifespan Event Loop**:
  - Seeds 15 historical telemetry frames for each registered connector on startup.
  - Spawns a background asynchronous task (`telemetry_loop`) that queries all attached connectors every 4.0 seconds and records standardized observations into `PORTAL_REGISTRY`.
- **CORS & Middleware**:
  - Permissive CORS enabling cross-origin communication with local Streamlit dashboards, Next.js apps, and static websites.
  - Intercepts requests with `PortalPulseSessionMiddleware` for active session and concurrency tracking.
- **Static Asset Serving**:
  - Mounts `/static` and `/assets` from `website/`.
  - Mounts `/portals/nirantar` serving the compiled React build from `/home/pratay-karali/Desktop/NIRANTAR/frontend/dist`.
  - Mounts `/portals/demo` serving HTML demo portals.

---

### 4.2 Control Plane Registry, Ring Buffer & Connection Lifecycle

Located in `backend/control_plane/registry.py` (558 lines):
- **Singleton `PORTAL_REGISTRY`**:
  - Thread-safe coordination across all connected portals.
- **Dual-Tier Telemetry Storage**:
  - *Tier 1: Hot In-Memory Ring Buffer*: `collections.deque(maxlen=1800)` per portal (stores up to 2.5 hours of 5-second telemetry in RAM).
  - *Tier 2: Persistent SQLite WAL*: Written to `backend/data/portal_telemetry.db` (`telemetry_history` table).
- **11-Stage Connection Lifecycle State Machine**:
  `DISCOVERING` → `AUTHENTICATING` → `SCHEMA_VALIDATED` → `CAPABILITIES_DISCOVERED` → `DEPENDENCIES_DISCOVERED` → `TELEMETRY_VERIFIED` → `HEALTH_CHECKED` → `CONNECTED` → `TELEMETRY_LOST` → `DEGRADED` → `OFFLINE`.

---

### 4.3 Dynamic NetworkX Topological Dependency Engine

Located in `backend/control_plane/dynamic_graph.py` (133 lines):
- Constructs an in-memory NetworkX Directed Acyclic Graph (`nx.DiGraph`) dynamically from any portal's declared `DependencyGraphSpec`.
- **Topological Depth Analysis**: Calculates topological distance of every microservice tier from the ingress entrypoint.
- **Dynamic Stress Propagation**: Evaluates normalized stress scores $[0.0 \to 1.0]$ across tiers based on live telemetry (e.g. associating DB latency with storage nodes, 5xx errors with ingress gateways, and CPU/RAM with backend worker nodes).

---

### 4.4 Capability Discovery & The Action Masker Engine

Located in `backend/control_plane/action_masker.py` (141 lines):
- Solves the problem of AI models recommending actions that the host portal cannot perform.
- Maps declared `PortalCapabilities` into a boolean mask vector across the 11 discrete `SREAction` types.
- **Probability Re-normalization**:
  - Zeroes out probabilities for unsupported actions.
  - Re-normalizes the remaining probability mass over permitted actions.
  - If a raw action is masked out, diverts to the highest-confidence permitted action and provides a human-readable `masking_rationale`.

---

### 4.5 Statistical Normal Operating Baseline Engine

Located in `backend/control_plane/baseline.py` (91 lines):
- Establishes empirical baseline distributions for each portal during initial quiet periods:
  - Nominal RPS, P50, P95, and P99 latency.
  - Nominal CPU %, RAM %, and error rates.
  - Computes dynamic warning thresholds ($3.5\times \text{P95}$) and critical thresholds ($10\times \text{P95}$).

---

### 4.6 Pluggable Reference Connectors (Nirantar, College, E-Commerce, Gov)

All connectors implement `BasePortalConnector` (`portalpulse_sdk/interface.py`):
1. **`NirantarConnector` (`backend/connectors/nirantar.py`)**:
   - Capabilities: Horizontal scaling ($4 \to 32$ pods), Redis caching, request queues, read replicas, rate limiting, waiting room.
   - Actuators: Dynamically adjusts pod count, diverts read traffic, purges cache, activates token bucket.
2. **`CollegePortalConnector` (`backend/connectors/college_portal.py`)**:
   - Capabilities: Constrained monolithic stack. `caching=False`, `database_replica=False`.
   - Actuators: Scales PHP workers ($2 \to 16$), enables fair queue waiting room, activates static fallback pages.
3. **`ECommerceConnector` (`backend/connectors/ecommerce.py`)**:
   - Capabilities: Microservices stack. `database_replica=True`, `caching=True`.
   - Actuators: Diverts search/catalog reads to replica, scales checkout pods, activates rate limits.
4. **`GovPortalConnector` (`backend/connectors/gov_portal.py`)**:
   - Capabilities: Public utility stack with strict 99.99% availability requirements.
   - Actuators: Activates edge rate limiting, static form degradation, queue throttling.

---

## 5. The 10 Autonomous SRE Intelligence Micro-Modules (M1–M9)

### 5.1 M1: APM Telemetry Ingestion & Portal Simulator

- **`collector.py` (10,275 bytes)**: Thread-safe ring buffer for raw telemetry ingestion. Calculates rolling derived features:
  - Error rate ($\frac{\text{HTTP 5xx}}{\text{Throughput}}$)
  - Traffic acceleration ($\frac{\Delta \text{RPS}}{\Delta t}$)
  - Saturation ratios ($\frac{\text{CPU}}{100}$, $\frac{\text{DB Connections}}{\text{Pool Size}}$)
- **`portal_simulator.py` (8,470 bytes)**: Synthetic telemetry generation engine reproducing non-linear physical system dynamics across nominal, burst, and failure scenarios.

---

### 5.2 M2: Multi-Horizon Predictive Forecaster (XGBoost / LightGBM / MLP)

- **`forecaster.py` (7,665 bytes)**: Multi-target regression engine predicting 10 continuous metrics across 5-min, 10-min, and 15-min horizons:
  - Future RPS, CPU %, RAM %, Latency, DB Connections, Error Rate, and Safe Capacity.
- **`feature_pipeline.py` (10,308 bytes)**: 28-feature pipeline extracting lag features, rolling standard deviations, cyclical hour/day sine-cosine encodings, and saturation ratios.
- **Model Benchmark**: Evaluated XGBoost ($R^2 = 0.9128$, $\text{MAE} = 131.39$), LightGBM, PyTorch Multi-Output MLP, and Random Forest.

---

### 5.3 M3: Unsupervised Outlier Detection (Isolation Forest)

- **`anomaly_detector.py` (8,689 bytes)**:
  - Powered by `sklearn.ensemble.IsolationForest`.
  - Trained strictly on nominal baseline telemetry (contamination rate $\nu = 0.03$).
  - Outputs a continuous anomaly score $[0.0 \to 1.0]$:
    - Nominal: Score $< 0.40$
    - Suspicious: $0.40 \le \text{Score} \le 0.65$
    - Outlier Alert: $\text{Score} > 0.65$
  - Inference latency: $0.582\text{ ms}$.

---

### 5.4 M4: Root Cause Analysis (XGBoost 8-Class Classifier & Causal DAG)

- **`rca_classifier.py` (11,014 bytes)**:
  - Multi-class XGBoost model attributing anomalies to 8 root failure categories:
    1. `NORMAL`
    2. `TRAFFIC_SPIKE`
    3. `API_CPU`
    4. `DATABASE`
    5. `NETWORK`
    6. `MEMORY`
    7. `QUEUE_OVERLOAD`
    8. `DEPENDENCY_FAILURE`
  - Performance: Macro $F_1 = 0.9996$, inference latency $0.765\text{ ms}$.
- **`dependency_graph.py` (13,903 bytes)**:
  - Traverses the NetworkX topological causal graph from root storage nodes back to ingress edge nodes to identify the fault origin tier.

---

### 5.5 M5: Tactical Action Intelligence Policy Network (PyTorch RTX 2050 CUDA)

- **`policy_net.py` & `action_engine.py` (17,796 bytes)**:
  - Deep PyTorch Multi-Layer Perceptron (MLP) with BatchNorm, Dropout (0.2), and Kaiming He initialization.
  - Hardware accelerated on the **NVIDIA GeForce RTX 2050 GPU (4GB VRAM)** via CUDA.
  - Maps a 13-dimensional unified system state vector into softmax probabilities over the 11 discrete `SREAction` types.
  - Trained on 25,000 synthetic state-action tuples codified from expert SRE playbooks and `secure_action.md`.
  - Performance: Test accuracy $99.52\%$, inference latency $0.314\text{ ms}$.

---

### 5.6 M5.5: AI SRE Operations Copilot & RAG Knowledge Base

- **`copilot.py` (15,061 bytes) & `knowledge_base.py` (8,198 bytes)**:
  - Natural language conversational assistant for human SRE operators.
  - Intent classification: `ROOT_CAUSE_QUERY`, `FORECAST_QUERY`, `ACTION_QUERY`, `STATUS_CHECK`, `DOCS_QUERY`, `GENERAL_SRE`.
  - **Retrieval-Augmented Generation (RAG)**: Uses TF-IDF and cosine similarity to index and retrieve technical guidelines from `secure_action.md` (token bucket mechanics, circuit breakers, anycast routing, load shedding).
  - Context grounding: Gathers live state from M1 (telemetry), M2 (forecast), M3 (anomaly), M4 (RCA), and M5 (action policy) to answer questions with zero hallucination.

---

### 5.7 M6: Deterministic Safety Layer (Zero-ML Guardrails & Token Bucket)

- **`guardrails.py` (13,135 bytes)**:
  - Enforces the **Zero-ML in Execution Path** mandate.
  - **Confidence Gate**: Blocks automated execution if policy network confidence $< 80\%$.
  - **Flapping Prevention**: Enforces a strict 300-second (5-minute) per-action cooldown to prevent cascading oscillations.
  - **Hard Replica Bounds**: Worker pods restricted to $[2, 24]$.
  - **Edge Token Bucket**: Capacity 5,000 tokens, 1,000 tokens/sec refill rate.
  - **Fail-Safe Circuit Breaker**: State transitions `CLOSED` → `OPEN` → `HALF_OPEN` when consecutive 5xx errors exceed 5 or error rate exceeds 8%.
  - **2-Phase Human-in-the-Loop (HITL) Store**: Thread-safe in-memory approval queue with 300-second TTL.

---

### 5.8 M7: Closed-Loop Actuator & Feedback Stabilization Trajectory

- **`actuator.py` (10,138 bytes)**:
  - Simulates non-linear physical system recovery over a 4-step convergence trajectory ($t+0\text{s} \to t+180\text{s}$):
    - Example: `SCALE_OUT_WORKERS` reduces CPU from $92.4\% \to 64.2\%$ and latency from $2,450\text{ms} \to 430\text{ms}$.
    - Example: `DIVERT_READS_TO_REPLICA` reduces DB latency from $420\text{ms} \to 35\text{ms}$.
  - Feeds stabilized metrics back into the M1 collector ring buffer to close the control loop.
  - Maintains an immutable in-memory audit log of all actuations.

---

### 5.9 M8: Chaos Engineering Lab & Analytical M/M/c Knee Curvature

- **`chaos_engine.py` (7,469 bytes)**:
  - Injects 8 operational stress scenarios:
    1. `NORMAL`: Baseline diurnal traffic.
    2. `RESULT_RUSH`: 50,000 concurrent user surge simulating exam result day.
    3. `DATABASE_LOCK_JAM`: Row-lock contention and pool exhaustion.
    4. `CPU_BURST_HOTSPOT`: RegEx / cryptographic CPU saturation.
    5. `MEMORY_LEAK_SLOW`: Gradual heap exhaustion triggering OOM killer.
    6. `NETWORK_PACKET_DROP`: 20% egress packet loss and SYN retransmits.
    7. `DEPENDENCY_5XX_OUTAGE`: Downstream authentication microservice failure.
    8. `CHAOS_MONKEY_POD_KILL`: Sudden pod termination under load.
  - **Analytical $M/M/c$ Queuing Knee-Point Detection**:
    - Calculates mathematical curvature $\frac{d^2 \text{Latency}}{d \text{RPS}^2}$.
    - Identifies the saturation knee point ($RPS_{\text{knee}} = \mu \cdot c \cdot 0.82$).
    - Issues proactive pre-saturation alerts before latency explodes.

---

### 5.10 M9: MLOps Drift Governance (KS-Test, PSI & Model Registry)

- **`drift_detector.py` (9,911 bytes)**:
  - **Two-Sample Kolmogorov-Smirnov (KS) Test**: Compares incoming live telemetry distributions against the frozen training baseline (`Module1_Data/train.csv`). Triggers retrain alert when $p\text{-value} < 0.01$.
  - **Population Stability Index (PSI)**: Quantile-based shift calculation ($\text{PSI} < 0.10$ healthy, $0.10 \le \text{PSI} \le 0.25$ moderate drift, $\text{PSI} > 0.25$ significant drift).
  - **Production Model Registry**: Tracks versioning, training dates, inference latency SLAs, and performance metrics across all 4 machine learning models:
    1. `PortalPulse-MultiHorizon-XGBoost` (v2.0.0)
    2. `PortalPulse-IsolationForest-Detector` (v2.0.0)
    3. `PortalPulse-XGBoost-RCA` (v2.0.0)
    4. `PortalPulse-ActionPolicy-MLP` (v2.0.0)

---

## 6. PortalPulse Universal Connector SDK (`portalpulse_sdk`)

The SDK provides client-side instrumentation for any host portal without hardcoded dependencies:

### 6.1 ASGI/WSGI Active Session & In-Flight Concurrency Middleware

Located in `portalpulse_sdk/middleware.py` (242 lines):
- **`PortalPulseSessionMiddleware`**: Standard ASGI middleware for FastAPI, Starlette, and Quart applications.
- **Strict Metric Differentiation**:
  1. *Active Sessions*: Unique sessions active within a sliding 30-second window. Identity hierarchy:
     $$\text{Bearer JWT Token} \longrightarrow \text{Session Cookie} \longrightarrow \text{HMAC-SHA256 Anonymized IP+UA Fallback}$$
     Sets `pp_anon_sid` cookie on the response if no identifier exists.
  2. *In-Flight Requests*: Tracks concurrent transactions currently executing in server threads (`_in_flight`).
  3. *Latency Reservoir Sampling*: Rolling reservoir (size 2,000) measuring empirical P50, P95, and P99 response times.

---

### 6.2 Client Agent Daemon & Heartbeat Loop

Located in `portalpulse_sdk/agent.py` (233 lines):
- Embeddable background daemon for web frameworks.
- Auto-registers the host portal with the Control Plane upon launch (`POST /api/v1/portals/register`).
- Runs a daemon background thread streaming `UniversalTelemetry` frames to the Control Plane every 5 seconds.
- Registers custom action execution handlers for remote SRE actuation.

---

### 6.3 Hardware Discovery & Linux cgroup v1/v2 Quota Detection

Located in `portalpulse_sdk/discovery.py` (154 lines):
- `detect_cgroup_limits()`:
  - Inspects `/sys/fs/cgroup/cpu.max` and `/sys/fs/cgroup/memory.max` for Linux **cgroups v2**.
  - Inspects `/sys/fs/cgroup/cpu/cpu.cfs_quota_us` and `/sys/fs/cgroup/memory/memory.limit_in_bytes` for Linux **cgroups v1**.
  - Calculates effective core quotas and RAM ceilings inside Docker and Kubernetes containers.
- `discover_resource_envelope()`:
  - Queries physical CPU cores, logical execution cores, total RAM, disk capacity, process worker counts, and database pool limits.

---

### 6.4 Out-of-Process Capacity Benchmark Worker (`scripts/load_worker.py`)

Located in `scripts/load_worker.py` (444 lines):
- Independent OS process ensuring load generation CPU does not skew server telemetry.
- Generates stepped virtual user (VU) populations using asynchronous HTTP connections (`httpx.AsyncClient`).
- Multi-persona traffic:
  - *Students* verifying exam results (`/portals/demo/college/index.html`)
  - *Shoppers* checking out products (`/portals/demo/ecommerce/index.html`)
  - *Citizens* verifying public records (`/portals/demo/gov/index.html`)
- Tracks Little's Law dynamics ($L = \lambda \cdot W$) and detects degradation knee points where second derivative latency explodes.
- Exports standard `CapacityProfile` JSON to `/tmp/portalpulse_benchmarks/profile_{portal_id}.json`.

---

## 7. Database Architecture, Hybrid Redis Caching & Quantum Security

Located in `dashboard/db.py` (1,129 lines):

### 7.1 SQLite WAL Schema & Query Audit Trail

- Persistent on-disk database at `dashboard/portalpulse.db`.
- Configured with `PRAGMA journal_mode = WAL` (Write-Ahead Logging), `PRAGMA synchronous = NORMAL`, and `PRAGMA busy_timeout = 5000`.
- Tables:
  1. `students`: `id`, `enrollment_no` (indexed), `name`, `email`, `department`, `year`, `semester`, `cgpa`, `status`, `created_at`.
  2. `academic_results`: `id`, `student_id` (FK, indexed), `semester`, `course_code`, `course_name`, `credits`, `grade_point`, `grade_letter`, `exam_date`.
  3. `faculty`: `id`, `faculty_id` (indexed), `name`, `email`, `department`, `designation`, `courses_taught`, `created_at`.
  4. `query_audit_logs`: `id`, `enrollment_no`, `query_type`, `duration_ms`, `cache_hit` (0/1), `timestamp` (indexed).

---

### 7.2 Hybrid Redis Caching Engine with In-Memory LRU Fallback

- **Primary**: Connects to remote Redis server (`REDIS_HOST`, `REDIS_PORT`, default `localhost:6379`).
- **Fallback**: Thread-safe in-memory cache (`_InMemoryCache`) with Least Recently Used (LRU) eviction and Time-to-Live (TTL) expiration (default 300 seconds).
- **Performance**:
  - Cold SQLite join query: $\sim 15\text{ ms} \to 35\text{ ms}$.
  - Warm Redis/in-memory cache hit: $< 0.8\text{ ms}$.
  - Speedup factor: **15x to 40x faster**.

---

### 7.3 Cryptographic Access Tokens & Constant-Time Verification

- Uses constant-time string comparison (`hmac.compare_digest`) to prevent timing side-channel attacks.
- Tokens:
  - Admin: `ADM-SEC-7F9A2B81C3D4`
  - Faculty: `FAC-SEC-5E6C1D94A8B2`
  - Student: `STU-SEC-3B8A7F1C9E20`
- Backward compatibility: Supports legacy `*-QKEY-*` strings.

---

## 8. Data Science, Datasets & Academic Syllabus Mapping

### 8.1 Master Telemetry Dataset (`Module1_Data`) & Split Manifest

- **Master Clean Dataset**: `Module1_Data/master_clean.csv` (39,584 clean minute-by-minute telemetry rows, 28 consecutive days).
- **Temporal Splitting (`split_manifest.json`)**:
  - *Train*: 28,720 rows (June 16 – July 5, 2025).
  - *Validation*: 4,305 rows (July 6 – July 8, 2025).
  - *Test*: 6,559 rows (July 9 – July 13, 2025).
  - Avoids data leakage by using strict chronological time boundaries rather than random shuffles.
- **Features**: `timestamp`, `hour`, `day_of_week`, `is_weekend`, `is_result_window`, `concurrent_users`, `requests_per_sec`, `cpu_usage`, `memory_usage`, `network_usage`, `latency_ms`, `error_rate`, `safe_capacity`, `risk_level`.

---

### 8.2 5-Model Empirical Evaluation & Benchmarks

| Model Architecture | Model Family | Test MAE (users) | Test $R^2$ | Inference Speed | Selection Status |
|---|---|---|---|---|---|
| **XGBoost** | Gradient Boosted Trees | **131.39** | **0.9128** | 0.012 ms | **Selected Production Top Performer** |
| **LightGBM** | Histogram GBDT | 134.10 | 0.9102 | 0.008 ms | Fast Edge Candidate |
| **PyTorch Multi-Output MLP** | Deep Neural Net (BatchNorm+He+Dropout) | 139.60 | 0.9015 | 0.015 ms | Optimized Deep Learning |
| **Random Forest** | Bagged Ensemble | 142.50 | 0.8940 | 0.045 ms | Robust Ensemble Baseline |
| **Linear / Ridge** | Regularized Linear | 284.70 | 0.5560 | 0.002 ms | Under-fitting Linear Baseline |

---

### 8.3 Syllabus Mapping (Weeks 1 through 5)

- **Week 1 (Module 1: Neural Network Foundations)**:
  - ANN, MLP, activation functions (ReLU, Sigmoid, Tanh), optimizers (Adam, SGD), loss tracking. Delivered in `week1/team2_ml/` and `week1/team3_dashboard/app_week1.py`.
- **Week 2 (Module 2: Deep Learning Optimization & Telemetry Intelligence)**:
  - Backpropagation, Xavier/He weight initialization, BatchNorm, Dropout, Multi-Output architecture, coupled telemetry synthesizer, 5-model benchmark. Delivered in `week2/team2_ml/` and `week2/team3_dashboard/app.py`.
- **Week 2.5 (Module 2.5: Real Database, Quantum Keys & High Concurrency)**:
  - SQLite WAL persistence, Redis caching, 3-role persona gateway, 10,000 VU load architecture. Delivered in `dashboard/db.py` and `week2.5/README.md`.
- **Week 3 (Module 3 & M4: Detective Layer)**:
  - Unsupervised Anomaly Detection (`IsolationForest`), XGBoost 8-class RCA attribution, and NetworkX topological causal DAG. Delivered in `backend/m3_anomaly_rca/`.
- **Week 4 (Module 5 & M6: Decision & Explanation Layer)**:
  - Deep PyTorch MLP Action Policy (CUDA RTX 2050 accelerated) and context-aware SRE Operations Copilot grounded in `secure_action.md`. Delivered in `backend/m4_action_intelligence/` and `backend/m5_assistant/`.
- **Week 5 (Master Autonomous Control Tower & Governance)**:
  - Zero-ML Deterministic Safety Guardrails (M6), Closed-Loop Actuator (M7), Chaos Engineering Lab (M8), MLOps Drift Governance (M9). Delivered in `backend/` and `week5/README.md`.

---

## 9. DevOps, Automation CLI, Testing & CI/CD

### Makefile Automation Targets

```bash
make lint        # Run Ruff linting check across entire repo
make format      # Auto-format codebase using Ruff
make type-check  # Run Mypy strict type checking on backend/ (0 errors across 48 source files)
make test        # Run full pytest test suite (19 test suites, 134 passed)
make test-cov    # Run pytest with terminal and HTML coverage report (86.69% coverage)
make ci          # Run lint, type-check, and test-cov (full local CI pipeline)
make dev-up      # Launch FastAPI Control Tower API server on port 8000
make run         # Launch Streamlit Control Tower Dashboard on port 8501
make bench       # Run 80-query Redis vs SQLite benchmark
make seed        # Populate SQLite DB with 200 synthetic student records
make docker-up   # Build and start Streamlit + Redis containers via Docker Compose
make docker-down # Teardown running Docker containers
make clean       # Remove cached bytecode and coverage artifacts
```

### Docker & Container Infrastructure
- **`Dockerfile`**: Builds Python 3.11-slim container with headless Streamlit configuration, installing `dashboard/requirements.txt`.
- **`docker-compose.yml`**: Deploys `portalpulse-dashboard` on port `8501` linked with `redis:7-alpine` on port `6379` with persistent volumes.

### Test Suite (`tests/`)
19 dedicated test suites:
- `test_auth_tokens.py`: HMAC token validation and backward compatibility.
- `test_quantum_keys.py`: Persona key verification.
- `test_db.py` & `test_db_adapter.py`: SQLite WAL transactions, thread contention, and cache fallback.
- `test_m1_monitoring.py` to `test_m6_to_m9_governance.py`: Complete unit and integration coverage for all 10 modules.
- `test_connector_architecture.py`: Multi-portal registration, capability masking, and dynamic DAG traversal.
- `test_closed_loop_pipeline.py`: End-to-end closed-loop sensing-to-actuation pipeline.

---

## 10. Comprehensive Critical Review: Strengths, Gaps, Bugs & Production Vulnerabilities

As an exhaustive critique of the PortalPulse implementation, here is an objective assessment of its strengths, incomplete implementations, architectural risks, and actual code defects:

### 🌟 Outstanding Engineering Strengths
1. **Architectural Separation of Concerns**: The strict isolation between predictive intelligence (M1–M5) and deterministic actuation (M6–M7) prevents machine learning model hallucinations from causing cascading infrastructure outages.
2. **Pluggable Connector Abstraction**: The `BasePortalConnector` contract cleanly decouples host applications from PortalPulse core logic. Adding a new portal requires zero modifications to core routing.
3. **Rigorous Statistical Grounding**: MLOps drift detection uses true mathematical formulas (Two-sample Kolmogorov-Smirnov test and Population Stability Index) rather than naive threshold heuristics.
4. **Active Session vs Throughput Nuance**: The SDK correctly distinguishes between active human sessions (30s window), arrival rate (RPS), and in-flight concurrency ($L$). Most APMs conflate these metrics.
5. **Full Enterprise Code Quality**: 100% adherence to `mypy --strict` across 48 backend source files, 86.69% test coverage, and clean Ruff formatting.

---

### ⚠️ Code Defects & Runtime Bugs Found

#### 1. Runtime JavaScript Error in `website/app.js`: Missing `initSpotlightNav`
- **Location**: `website/app.js`, line 1070.
- **Defect**: In `PortalApp.init()`, line 1070 calls `initSpotlightNav();`. However, `initSpotlightNav` is never defined anywhere in `app.js` or `index.html`.
- **Impact**: In a standard browser environment, this triggers an uncaught `ReferenceError: initSpotlightNav is not defined`, potentially halting JavaScript execution and breaking subsequent event listeners or polling loops.
- **Remedy**: Define `function initSpotlightNav() { ... }` or remove line 1070.

#### 2. Disconnection Between `docker-compose.yml` and FastAPI Gateway
- **Location**: `docker-compose.yml` and `Dockerfile`.
- **Defect**: The Dockerfile and compose configuration solely run the Streamlit dashboard on port `8501` (`streamlit run dashboard/app.py`). The core FastAPI Control Tower gateway (`backend/app.py`, port `8000`) and the web application (`website/`) are **omitted from the Docker Compose orchestration**.
- **Impact**: Deploying via `docker-compose up` will only launch the Streamlit frontend. The REST API, M1–M9 micro-services, and interactive HTML website will not be available in Docker without manual container expansion.
- **Remedy**: Add a `control-tower-api` service to `docker-compose.yml` exposing port `8000:8000` with `uvicorn backend.app:app`.

#### 3. Hardcoded "Quantum" Key Semantics vs Real Post-Quantum Cryptography
- **Location**: `dashboard/db.py` (`QUANTUM_KEYS`, `ROLE_ACCESS_TOKENS`) and `README.md`.
- **Defect**: The documentation advertises "256-bit Post-Quantum Symmetric Entropy Keys". In code, these are static alphanumeric strings (`ADM-SEC-7F9A2B81C3D4`, `STU-SEC-3B8A7F1C9E20`) validated via Python's standard `hmac.compare_digest`.
- **Impact**: While constant-time comparison prevents timing attacks, these are traditional pre-shared bearer keys (API tokens), not post-quantum algorithms (such as Kyber/ML-KEM or Dilithium/ML-DSA).
- **Remedy**: Update documentation to specify "High-Entropy HMAC-SHA256 Bearer Tokens" or integrate genuine liboqs/ML-KEM lattice key encapsulation.

#### 4. Simulated Telemetry Relief vs Real Infrastructure Mutators
- **Location**: `backend/m7_actuator/actuator.py` and `backend/connectors/*.py`.
- **Defect**: When an action like `SCALE_OUT_WORKERS` or `DIVERT_READS_TO_REPLICA` is executed, the actuator simulates metric relief by applying mathematical deltas to in-memory telemetry objects (`cpu_percent -= 18.5`, `latency_ms -= 45.0`). It does not invoke actual Kubernetes API calls (`client-go` / `kubectl scale deployment`), AWS Auto Scaling Group APIs, or NGINX upstream reconfiguration.
- **Impact**: Suitable for simulation, academic evaluation, and architectural demonstration, but requires production driver plugins (e.g. Kubernetes Client, AWS SDK, Redis Sentinel) to actuate real physical clusters.
- **Remedy**: Introduce an `InfrastructureDriver` interface with Kubernetes and Cloudflare drivers implementing `execute_physical_action()`.

#### 5. SQLite WAL Concurrency Ceiling Under 10,000+ Concurrent Virtual Users
- **Location**: `dashboard/db.py` (`portalpulse.db`).
- **Defect**: Although SQLite WAL mode allows concurrent readers alongside a single writer, high-frequency grade updates from hundreds of concurrent faculty members during an exam rush will encounter `sqlite3.OperationalError: database is locked` once write queues exceed the 5,000ms busy timeout.
- **Impact**: The SQLite backend will saturate under true 10,000 VU write load.
- **Remedy**: Migrate write traffic to the provided `PostgresAdapterStub` with PgBouncer connection pooling and read replicas for production deployments.

#### 6. Disconnected Academic Evolution Folders (`week3/`, `week4/`, `week5/`)
- **Location**: Top-level `week3/`, `week4/`, `week5/` directories.
- **Defect**: While `week1/` and `week2/` have independent subdirectories (`team1_data`, `team2_ml`, `team3_dashboard`), `week3/`, `week4/`, and `week5/` only contain single `README.md` files pointing back to `backend/m3_anomaly_rca`, `backend/m4_action_intelligence`, etc.
- **Impact**: Purely organizational inconsistency; all core code was consolidated into `backend/` rather than keeping weekly copies.

---

## 11. Conclusion & Master Feature Matrix

| Feature / Capability | Location | Implementation Type | Production Readiness |
|---|---|---|---|
| **Overview Command Center** | `website/index.html` (`#page-overview`) | Pure JS + SVG Charts | Ready (Production UI) |
| **Portals Fleet Directory** | `website/index.html` (`#page-portals`) | Pure JS + Card Grid | Ready |
| **Dynamic Topology DAG** | `backend/control_plane/dynamic_graph.py` | NetworkX DiGraph | Ready |
| **Telemetry Mode Switcher** | `website/app.js` (`setTelemetryMode`) | REST API + State | Ready |
| **Capacity Benchmark Console** | `website/index.html` & `load_worker.py` | Async HTTPX Process | Ready |
| **APM Monitoring Views** | `website/index.html` (`#page-monitoring`) | Polling SVG APM | Ready |
| **Incident Triage & RCA** | `website/index.html` (`#page-incidents`) | Master-Detail UI | Ready |
| **Action Center & Masker** | `backend/control_plane/action_masker.py` | Re-normalized Softmax | Ready |
| **4-Step Handshake Wizard** | `website/index.html` (`#page-integrations`) | Interactive Stepper | Ready |
| **Mascot Emotion Dock** | `website/app.js` (`switchBoyPose`) | Floating Widget | Ready (Visual Polish) |
| **Student Persona Workspace** | `dashboard/app.py` (Streamlit) | Real SQLite + Cache | Ready |
| **Faculty Grade Studio** | `dashboard/app.py` & `dashboard/db.py` | Real SQLite + Cache Invalidation | Ready |
| **Admin Control Tower** | `dashboard/app.py` (13 Views) | Full Streamlit Suite | Ready |
| **SQLite WAL Persistence** | `dashboard/db.py` | SQLite WAL + Indexes | Ready (Needs PG for >10k writes) |
| **Hybrid Redis Caching** | `dashboard/db.py` | Redis + Memory LRU | Ready |
| **Token-Based Auth (RBAC)** | `dashboard/db.py` | Constant-Time HMAC | Ready |
| **Multi-Horizon Forecaster** | `backend/m2_prediction/` | XGBoost ($R^2 = 0.913$) | Ready |
| **Anomaly Detector** | `backend/m3_anomaly_rca/` | Isolation Forest | Ready |
| **RCA Classifier** | `backend/m3_anomaly_rca/` | XGBoost 8-Class | Ready |
| **Action Policy Network** | `backend/m4_action_intelligence/` | PyTorch CUDA MLP | Ready |
| **AI SRE Copilot (RAG)** | `backend/m5_assistant/` | TF-IDF + Cosine RAG | Ready |
| **Deterministic Guardrails**| `backend/m6_safety_layer/` | Zero-ML Rules Engine | Ready |
| **Closed-Loop Actuator** | `backend/m7_actuator/` | 4-Step Stabilization | Simulated Delta (Needs Cloud Driver) |
| **Chaos Injection Lab** | `backend/m8_chaos_lab/` | 8 Scenarios + $M/M/c$ | Ready |
| **MLOps Drift Governance** | `backend/m9_mlops_drift/` | KS-Test + PSI | Ready |
| **Active Session Tracking** | `portalpulse_sdk/middleware.py` | Sliding 30s Window | Ready |
| **Container Quota Discovery**| `portalpulse_sdk/discovery.py` | Linux cgroup v1/v2 | Ready |
| **Reference Connectors** | `backend/connectors/` (4 Portals) | Subclasses of Base | Ready |
