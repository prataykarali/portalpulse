# Module 2 (Week 2): Deep Learning Optimization & Telemetry Intelligence

## Syllabus Coverage
- **Theory**: Backpropagation & Gradients $\rightarrow$ Weight Initialization (Default vs Xavier vs He) $\rightarrow$ Batch Normalization $\rightarrow$ Dropout & $L_2$ Regularization $\rightarrow$ Multi-Output Architectures.
- **Lab Concepts**: Gradient tracking, BatchNorm stability, Dropout generalization gaps, and shared-trunk multi-head predictions.
- **PortalPulse Application**: Transforming the baseline neural network into a robust, physically coupled telemetry simulation and deterministic decision engine.

---

## 1. Directory Structure

```
week2/
├── README.md                  # Week 2 documentation and execution guide
├── team1_simulation/          # Physically consistent telemetry engine
│   ├── scenario_profiles.py   # Academic workload scenarios (Result rush, Exam fees, etc.)
│   └── telemetry_synthesizer.py # Coupled telemetry generator
├── team2_ml/                  # Deep learning optimization experiments
│   ├── multi_output_mlp.py    # Shared-trunk PyTorch MLP with BatchNorm & Dropout
│   ├── experiment_initialization.py # Default vs Xavier vs He Normal comparison
│   ├── experiment_batchnorm.py      # BatchNorm vs No-BatchNorm stability
│   ├── experiment_dropout.py        # Dropout & Regularization analysis
│   ├── train_week2_model.py   # Primary multi-output training pipeline
│   ├── benchmark_5_models.py  # 5-Model empirical benchmark
│   ├── models/                # Saved Week 2 PyTorch model weights
│   └── results/               # Experiment logs & comparison JSONs
└── team3_dashboard/           # Week 2 Live Simulator & Decision Engine
    └── app.py                 # Interactive Streamlit dashboard
```

---

## 2. Experimental Benchmark Summary

### 1. Weight Initialization Benchmark
| Initialization | Final Val MSE Loss | Safe Capacity Test MAE (users) | Notes |
|---|---|---|---|
| **He / Kaiming Normal** | **0.068** | **145.2** | **Best**: Prevents vanishing/exploding variance in deep ReLU networks. |
| **Xavier / Glorot** | 0.076 | 158.6 | Balanced variance, slightly slower convergence on ReLU. |
| **Default Uniform** | 0.089 | 174.1 | Higher initial loss variance. |

### 2. Batch Normalization Benchmark
| Variant | Final Val MSE Loss | Safe Capacity Test MAE (users) |
|---|---|---|
| **With BatchNorm (`nn.BatchNorm1d`)** | **0.062** | **141.8** |
| **Without BatchNorm** | 0.076 | 158.6 |

### 3. Dropout & Regularization Benchmark
| Regularization Config | Train MSE | Val MSE | Generalization Gap | Test MAE (users) |
|---|---|---|---|---|
| **Dropout (0.15) + $L_2$ Decay ($10^{-4}$)** | 0.058 | **0.061** | **+0.003** (Minimal Overfitting) | **139.6** |
| **No Regularization** | 0.041 | 0.078 | +0.037 (Overfitting) | 162.3 |

### 4. 5-Model Architecture Comparison
| Model | Family | Test MAE (users) | Test $R^2$ | Inference Latency |
|---|---|---|---|---|
| **XGBoost** | Gradient Boosted Trees | **131.3** | **0.913** | 0.012 ms |
| **LightGBM** | Histogram GBDT | 134.1 | 0.910 | 0.008 ms |
| **PyTorch Multi-Output MLP** | Deep Neural Net (BatchNorm+He+Dropout) | 139.6 | 0.901 | 0.015 ms |
| **Random Forest** | Bagged Ensemble | 142.5 | 0.894 | 0.045 ms |
| **Linear / Ridge** | Linear Baseline | 284.7 | 0.556 | 0.002 ms |

---

## 3. How to Run Week 2

```bash
# 1. Run Initialization Experiments
python week2/team2_ml/experiment_initialization.py

# 2. Run BatchNorm Experiments
python week2/team2_ml/experiment_batchnorm.py

# 3. Run Dropout & Regularization Experiments
python week2/team2_ml/experiment_dropout.py

# 4. Train Final Week 2 Multi-Output PyTorch Model
python week2/team2_ml/train_week2_model.py

# 5. Run 5-Model Benchmark
python week2/team2_ml/benchmark_5_models.py

# 6. Launch Week 2 Live Simulator Dashboard
streamlit run week2/team3_dashboard/app.py
```
