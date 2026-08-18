# Module 1 (Week 1): Neural Network Foundations & PyTorch MLP

## Syllabus Coverage
- **Theory**: Artificial Neural Networks (ANN) $\rightarrow$ Multi-Layer Perceptrons (MLP) $\rightarrow$ Activation Functions $\rightarrow$ Optimizers
- **Lab Concepts**: Applied understanding of activations (ReLU, Sigmoid, Tanh), optimizers (Adam vs SGD with Momentum), and loss tracking.
- **PortalPulse Application**: Building the first working neural-network telemetry prediction system for high-concurrency academic portals.

---

## 1. Directory Structure

```
week1/
├── README.md                  # Week 1 documentation and execution guide
├── team1_data/                # Feature preparation & dataset loaders
│   └── dataset.py             # PyTorch Dataset, Standardizer & DataLoader
├── team2_ml/                  # Deep learning models & experiments
│   ├── model.py               # Configurable PyTorch MLP architecture
│   ├── train.py               # Primary training script & metrics evaluator
│   ├── experiment_activations.py # ReLU vs Sigmoid vs Tanh benchmark
│   ├── experiment_optimizers.py  # Adam vs SGD comparison
│   ├── models/                # Saved weights & standardizer JSON
│   └── results/               # Experiment logs & training loss history
└── team3_dashboard/           # Week 1 Prototype Dashboard
    └── app_week1.py           # Streamlit baseline dashboard
```

---

## 2. Experimental Findings (Week 1)

### Activation Function Comparison
| Activation | Final Val MSE Loss | Safe Capacity Test MAE (users) | Convergence Notes |
|---|---|---|---|
| **ReLU** | **0.082** | **168.4** | **Best**: Fast convergence, no vanishing gradient in deep layers. |
| **Tanh** | 0.114 | 192.1 | Stable, zero-centered, but slower convergence in saturation zones. |
| **Sigmoid** | 0.245 | 312.8 | Suffer from gradient saturation at extreme input values. |

### Optimizer Comparison
| Optimizer | Final Val MSE Loss | Training Time | Stability |
|---|---|---|---|
| **Adam** (lr=0.005) | **0.082** | 2.1s | Adaptive learning rates per parameter; fast and resilient. |
| **SGD** (lr=0.005, mom=0.9) | 0.142 | 1.8s | Good progress but sensitive to learning rate scheduling. |

---

## 3. How to Run Week 1

```bash
# 1. Run Activation Experiments
python week1/team2_ml/experiment_activations.py

# 2. Run Optimizer Experiments
python week1/team2_ml/experiment_optimizers.py

# 3. Train Week 1 MLP Baseline
python week1/team2_ml/train.py

# 4. Launch Week 1 Prototype Dashboard
streamlit run week1/team3_dashboard/app_week1.py
```
