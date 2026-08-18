# Model Benchmark: 5 Architecture Comparison for Safe Capacity Prediction

## Overview
To establish a rigorous, defensible ML foundation for PortalPulse Module 2, we evaluated 5 distinct regression model families on the frozen time-split dataset (28,720 training records, 4,305 validation records, and 6,559 untouched test records).

Target variable: `safe_capacity` (Maximum concurrent users sustainable before SLA breach: latency < 800ms, CPU < 85%, error rate < 1%).

---

## 1. Benchmark Comparison Results

| Architecture | Model Family | Test MAE (users) | Test RMSE (users) | Test $R^2$ | Inference Speed | Operational Strengths & Tradeoffs |
|---|---|---|---|---|---|---|
| **XGBoost** | Gradient Boosted Trees | **131.3** | **167.3** | **0.913** | ~0.012 ms/req | **Top Performer**: Exceptional capture of nonlinear calendar & saturation knees; native tree export. |
| **LightGBM / HistGB** | Histogram GBDT | 134.1 | 170.8 | 0.910 | ~0.008 ms/req | **Fastest GBDT**: Extremely low training and inference latency with near-identical accuracy. |
| **Random Forest** | Bagged Ensemble | 142.5 | 185.2 | 0.894 | ~0.045 ms/req | **Robust**: Resilient to outliers and variance; slightly higher memory footprint. |
| **MLP / ANN** | Deep Feedforward Neural Net | 168.4 | 215.6 | 0.856 | ~0.020 ms/req | **Continuous**: Smooth interpolation across high-dimensional space; requires feature normalization. |
| **Linear / Ridge** | Regularized Linear Model | 284.7 | 378.1 | 0.556 | ~0.002 ms/req | **Baseline**: Fast and interpretable, but fails to capture sharp nonlinear queuing knee transitions. |

*Note: In-sample cross-validation $R^2$ on the full historical table is 0.969; the time-split test set ($R^2 = 0.913$) reflects true out-of-time calendar generalization.*

---

## 2. Engineering Analysis of the 5 Architectures

### 1. Linear / Ridge Regression (Baseline)
- **Why it struggles**: System saturation is fundamentally non-linear. The relationship between concurrent users and latency remains flat (~40ms) until ~7,500 users, then violently surges past 800ms into thousands of milliseconds. Linear models underpredict during normal periods and severely underpredict risk during overload spikes.

### 2. Random Forest Regressor
- **Behavior**: Averages 100 deep decision trees. Handles multi-collinearity between `concurrent_users` and `requests_per_sec` effectively.
- **Tradeoff**: Cannot extrapolate beyond the maximum safe capacity observed in training data, but provides stable bounds.

### 3. XGBoost Regressor (Production Selected Model)
- **Behavior**: Sequentially optimizes residuals using gradient boosting with second-order Taylor approximations.
- **Why it wins**: Best feature importance attribution (`is_result_window` 95.1% gain share, followed by `hour` and `latency_ms`). Consistently achieves lowest MAE (131.3 users on test split).

### 4. LightGBM / Histogram GBDT
- **Behavior**: Uses histogram-based binning of continuous features, reducing memory churn and boosting inference throughput by 30–40% compared to standard exact-split tree building.
- **Best Use Case**: Edge prediction microservices requiring sub-millisecond evaluation latency.

### 5. Multi-Layer Perceptron (MLP / ANN)
- **Architecture**: Input (11 features) $\rightarrow$ Dense(64, ReLU) $\rightarrow$ Dense(32, ReLU) $\rightarrow$ Linear(1).
- **Behavior**: Captures continuous multi-variate interactions across CPU, RAM, Network, and Latency.
- **Tradeoff**: Requires strict `StandardScaler` normalization; sensitive to extreme out-of-distribution values during flash spikes.

---

## 3. Recommended Production Selection for Module 2

**Primary Selected Engine**: **XGBoost Regressor / LightGBM**
- **Artifact**: `traffic_bot_model/xgboost_safe_capacity.json`
- **Inference Pipeline**: Wrapped inside the deterministic Decision Engine to ensure explainable `SAFE`, `WARNING`, and `CRITICAL` state transitions.
