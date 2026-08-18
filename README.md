# PortalPulse: AI-Driven Traffic Intelligence & Capacity Protection

> **Predictive Traffic Intelligence, Deep Learning Telemetry Simulation & SLA-Preserving Capacity Control for Academic Portals.**

---

## 🏛️ Syllabus Mapping & Academic Structure

| Module | Focus Area | Syllabus Topics Covered | PortalPulse Real-World Implementation |
|---|---|---|---|
| **Module 1 (Week 1)** | **Neural Network Foundations** | ANN, MLP, Activation Functions (ReLU, Sigmoid, Tanh), Optimizers (Adam, SGD), Loss Tracking | Baseline PyTorch MLP predicting CPU, Latency, and Safe Capacity from telemetry. |
| **Module 2 (Week 2)** | **Deep Learning Optimization & Telemetry Intelligence** | Backpropagation, Weight Initialization (Xavier, He), BatchNorm, Dropout, Multi-Output Architecture | Coupled Telemetry Synthesizer, 5-Model Benchmark Suite, and Deterministic Decision Engine. |

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
├── dashboard/                     # Root Production Dashboard (`app.py`)
├── traffic_bot_model/             # Exported model weights, schemas & benchmark metrics
└── docs/                          # In-depth architectural & planning documents
    ├── model_comparison.md        # Detailed 5-Model Empirical Evaluation
    └── module2_plan.md            # Module 2 Master Engineering Roadmap
```

---

## 🚀 Quickstart Guide

### 1. Launch the Week 1 Prototype Dashboard
```bash
streamlit run week1/team3_dashboard/app_week1.py
```

### 2. Launch the Week 2 Live Simulator & Decision Engine
```bash
streamlit run week2/team3_dashboard/app.py
# Or launch from root:
streamlit run dashboard/app.py
```

### 3. Run Deep Learning Experiments & Benchmarks
```bash
# Week 1 Experiments
python week1/team2_ml/experiment_activations.py
python week1/team2_ml/experiment_optimizers.py
python week1/team2_ml/train.py

# Week 2 Experiments
python week2/team2_ml/experiment_initialization.py
python week2/team2_ml/experiment_batchnorm.py
python week2/team2_ml/experiment_dropout.py
python week2/team2_ml/train_week2_model.py
python week2/team2_ml/benchmark_5_models.py
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
