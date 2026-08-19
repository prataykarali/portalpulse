# PortalPulse: AI-Driven Traffic Intelligence & Capacity Protection

> **Predictive Traffic Intelligence, Deep Learning Telemetry Simulation, Real Database Persistence & Quantum-Secure Multi-Role Orchestration for Academic Portals.**

---

## 🏛️ Syllabus Mapping & Academic Structure

| Module | Focus Area | Syllabus Topics Covered | PortalPulse Real-World Implementation |
|---|---|---|---|
| **Module 1 (Week 1)** | **Neural Network Foundations** | ANN, MLP, Activation Functions (ReLU, Sigmoid, Tanh), Optimizers (Adam, SGD), Loss Tracking | Baseline PyTorch MLP predicting CPU, Latency, and Safe Capacity from telemetry. |
| **Module 2 (Week 2)** | **Deep Learning Optimization & Telemetry Intelligence** | Backpropagation, Weight Initialization (Xavier, He), BatchNorm, Dropout, Multi-Output Architecture | Coupled Telemetry Synthesizer, 5-Model Benchmark Suite, and Deterministic Decision Engine. |
| **Module 2.5 (Week 2.5)** | **Real Database, Quantum Keys & High Concurrency** | SQLite WAL, Hybrid Redis Caching, 3-Role Quantum-Resistant Symmetric Keys, 10k VU Load Architecture | Persistent Student & Grade DB, Redis Caching, Student/Faculty/Admin Personas, and Non-DDoS Load Testing Blueprint. |

---

## 📁 Repository Structure

```
portalpulse/
├── Module1_Data/                  # Frozen master dataset & splits (39,584 clean minute records)
│
├── week1/                         # MODULE 1: Neural Network Foundations
│   ├── README.md                  # Week 1 Guide & Experiment Summary
│   ├── team1_data/                # Dataset & PyTorch DataLoader
│   ├── team2_ml/                  # MLP, Activations (ReLU/Sigmoid/Tanh), Optimizers (Adam/SGD)
│   └── team3_dashboard/           # Week 1 Prototype Dashboard (`app_week1.py`)
│
├── week2/                         # MODULE 2: Optimization & Live Telemetry Simulation
│   ├── README.md                  # Week 2 Guide & 5-Model Benchmark
│   ├── team1_simulation/          # Scenario Profiles & Coupled Telemetry Synthesizer
│   ├── team2_ml/                  # Xavier/He Init, BatchNorm, Dropout, Multi-Output MLP, 5-Model Benchmark
│   └── team3_dashboard/           # Week 2 Live Simulator & Decision Engine (`app.py`)
│
├── week2.5/                       # MODULE 2.5: Real Database, Quantum Keys & 10k User Architecture
│   └── README.md                  # Detailed Week 2.5 Architecture, Database Schema & Load Testing Blueprint
│
├── dashboard/                     # Root Production Dashboard (`app.py`) & Database Engine (`db.py`)
├── traffic_bot_model/             # Exported model weights, schemas & benchmark metrics
└── docs/                          # In-depth architectural & planning documents
    ├── model_comparison.md        # Detailed 5-Model Empirical Evaluation
    └── module2_plan.md            # Module 2 Master Engineering Roadmap
```

---

## 🔐 3-Role Quantum-Resistant Access Control

PortalPulse features a 3-role persona gateway with 256-bit post-quantum symmetric entropy keys:

| Persona | Quantum Access Key | Scoped Capabilities |
|---|---|---|
| **🎓 Student** | `STU-QKEY-3B8A7F1C9E20` | View personal profile, enrolled course marks, CGPA, and sub-millisecond cached queries. |
| **👨‍🏫 Faculty** | `FAC-QKEY-5E6C1D94A8B2` | Departmental course roster, grade entry/publishing form with real-time cache invalidation. |
| **🛡️ Master Admin (You)** | `ADM-QKEY-7F9A2B81C3D4` | Global control tower, Live Traffic Simulator, All DB tables, Telemetry, and Defense Modes. |

---

## 🗄️ Real Relational Database & Hybrid Redis Caching Layer

- **SQLite WAL Mode (`dashboard/portalpulse.db`)**: Persistent on-disk storage for `students`, `academic_results`, and `query_audit_logs`.
- **Hybrid Redis Cache**: Automatic remote Redis connection with in-memory LRU/TTL fallback, reducing query latency from $\sim 30\text{ ms}$ on cold joins to $< 1\text{ ms}$ on cache hits.
- **Empirical DB Benchmark**: Built-in 60-query load test demonstrating cache speedup.

---

## 🚀 Quickstart Guide

### 1. Launch the Root Production Dashboard (All Week 2.5 Features)
```bash
streamlit run dashboard/app.py
```

### 2. Launch Week-Specific Prototypes
```bash
# Week 1 Prototype
streamlit run week1/team3_dashboard/app_week1.py

# Week 2 Simulator
streamlit run week2/team3_dashboard/app.py
```

---

## 🔬 Benchmark Summary: 5 Architecture Comparison

| Architecture | Model Family | Test MAE (users) | Test $R^2$ | Inference Speed | Status |
|---|---|---|---|---|---|
| **XGBoost** | Gradient Boosted Trees | **131.3** | **0.913** | 0.012 ms | **Selected Top Performer** |
| **LightGBM** | Histogram GBDT | 134.1 | 0.910 | 0.008 ms | Fast Candidate |
| **PyTorch Multi-Output MLP** | Deep Neural Net (BatchNorm+He+Dropout) | 139.6 | 0.901 | 0.015 ms | Optimized Deep Learning |
| **Random Forest** | Bagged Ensemble | 142.5 | 0.894 | 0.045 ms | Robust Baseline |
| **Linear / Ridge** | Regularized Linear | 284.7 | 0.556 | 0.002 ms | Linear Baseline |

---

## ⚡ Architectural Position: PortalPulse vs Edge CDNs (Cloudflare)
- **Edge CDN (Cloudflare)**: Mitigates L3/L4 DDoS attacks, caches static assets, but is blind to internal ERP database query queues, transaction locks, and relational table saturation.
- **PortalPulse Application Layer**: Monitors server telemetry (CPU, RAM, M/M/1 latency knee), forecasts database pool starvation minutes in advance, and enforces token-bucket admission and priority queues before the backend database crashes.
