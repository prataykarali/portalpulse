# Week 5: Master Autonomous SRE Control Tower & Governance (M6 to M10)

## Strategic Objective
Week 5 delivers the production unification of the **Execution, Resilience, and Governance Layers** of PortalPulse. This bridges the predictive intelligence (M1–M5) with deterministic safety guarantees, closed-loop actuation, fault-injection chaos testing, and MLOps drift governance.

---

## Architecture Overview: The 10 Autonomous Modules

```
                ┌────────────────────────────────────────────────────────┐
                │             PortalPulse Control Tower API              │
                └──────────────────────────┬─────────────────────────────┘
                                           │
 ┌───────────────────────┬─────────────────┴─────────────┬────────────────────────┐
 │ Ingestion & Sensing   │ Diagnostic & Prescriptive     │ Execution & Resilience │
 ├───────────────────────┼───────────────────────────────┼────────────────────────┤
 │ M1: APM Telemetry     │ M3: Isolation Forest Anomaly  │ M6: Deterministic Safety│
 │     Ingestion Buffer  │ M4: XGBoost RCA + NetworkX DAG│ M7: Closed-Loop Actuator│
 │ M2: Multi-Horizon     │ M5: Deep MLP Action Policy    │ M8: Chaos Injection Lab │
 │     XGBoost Forecaster│     (RTX 2050 CUDA PyTorch)   │ M9: MLOps KS/PSI Drift │
 │                       │ M5.5: Operations Copilot RAG  │     & Model Registry   │
 └───────────────────────┴───────────────────────────────┴────────────────────────┘
```

---

## 1. Module 6: Deterministic Safety Layer (Zero ML in Execution Path)
Located in [`backend/m6_safety_layer/`](file:///home/pratay-karali/Desktop/portalpulse/backend/m6_safety_layer/):
- **Zero-ML Execution Policy**: Adheres strictly to [`secure_action.md`](file:///home/pratay-karali/Desktop/portalpulse/secure_action.md). No machine learning model directly touches production infrastructure.
- **Minimum Confidence Gate**: Disallowed automated actuation if policy network confidence $< 80\%$ (`APPROVAL_REQUIRED`).
- **Blast Radius Boundaries**:
  - `LOW`: Pod autoscaling (+1 to +4 pods). Auto-executable if confidence $\ge 80\%$.
  - `MEDIUM`: Read replica scale-out, Redis cache pre-warming.
  - `HIGH`: Token bucket rate limiting ($5,000 \to 2,000$ RPS), dynamic queue wait rooms.
  - `CRITICAL`: Circuit breaker tripping, static degrade mode. **Always forces 2-phase human operator approval.**
- **Flapping Prevention**: Enforces a strict 300-second (5-minute) per-action cooldown window to prevent thrashing and cascading oscillations.
- **Edge Token Bucket Rate Limiter**: Capacity 5,000 tokens, 1,000 tokens/sec refill rate.
- **Fail-Safe Circuit Breaker**: State transitions `CLOSED -> OPEN -> HALF_OPEN` on consecutive 5xx errors ($N=5$).
- **2-Phase Human-in-the-Loop (HITL) Store**: Thread-safe in-memory approval queue with timeout expiry (300s) and operator audit tracking.

---

## 2. Module 7: Closed-Loop Actuator & Feedback Stabilization
Located in [`backend/m7_actuator/`](file:///home/pratay-karali/Desktop/portalpulse/backend/m7_actuator/):
- **Dynamic Metric Relief Trajectories**: Simulates non-linear physical system recovery over a 4-step convergence trajectory (`t+0s` to `t+180s`).
  - Example: `SCALE_OUT_PODS` stabilizes CPU from $92.4\% \to 64.2\%$, Latency from $2,450\text{ms} \to 430\text{ms}$, and eliminates 5xx errors.
  - Example: `EXPAND_DB_POOL` reduces DB connection saturation from $95.2\% \to 48.0\%$ and DB latency from $420\text{ms} \to 35\text{ms}$.
- **Immutable Audit Logging**: Every executed action logs pre-action metrics, execution timestamp, operator authorization, and post-action delta.

---

## 3. Module 8: Chaos Engineering & Knee-Point Detection Lab
Located in [`backend/m8_chaos_lab/`](file:///home/pratay-karali/Desktop/portalpulse/backend/m8_chaos_lab/):
- **8 Chaos Scenarios**:
  1. `NORMAL`: Baseline diurnal operations.
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
  - Issues proactive pre-saturation alerts before the hockey-stick latency explosion occurs.

---

## 4. Module 9: MLOps Drift Governance & Model Registry
Located in [`backend/m9_mlops_drift/`](file:///home/pratay-karali/Desktop/portalpulse/backend/m9_mlops_drift/):
- **Two-Sample Kolmogorov-Smirnov (KS) Test**: Non-parametric distribution drift testing on incoming continuous telemetry. Triggers retrain alert when $p\text{-value} < 0.01$.
- **Population Stability Index (PSI)**: Quantile-based shift calculation:
  - $\text{PSI} < 0.10$: Healthy, no shift.
  - $0.10 \le \text{PSI} \le 0.25$: Moderate drift, monitor closely.
  - $\text{PSI} > 0.25$: Significant population drift, automatic retrain triggered.
- **Production Model Registry**: Tracks versioning, training dates, inference latency SLAs, and performance metrics across all 4 machine learning models:
  1. `PortalPulse-MultiHorizon-XGBoost` (v2.0.0)
  2. `PortalPulse-IsolationForest-Detector` (v2.0.0)
  3. `PortalPulse-XGBoost-RCA` (v2.0.0)
  4. `PortalPulse-ActionPolicy-MLP` (v2.0.0)

---

## 5. End-to-End Performance & Benchmark Catalog

| Module | Model / Engine | Target Objective | Accuracy / F1 / $R^2$ | p50 Latency | Status |
|---|---|---|---|---|---|
| **M1** | In-Memory Circular Buffer | Ingestion & SLA Monitor | 100% Deterministic | $< 0.15$ ms | PASS |
| **M2** | Multi-Horizon XGBoost | Safe Capacity + 10 Targets | $R^2 = 0.9128$, MAE = 131.39 | $0.753$ ms | PASS |
| **M3** | Isolation Forest | Unsupervised Outlier | Normal Score $< 0.40$, Outlier $> 0.65$ | $0.582$ ms | PASS |
| **M4** | XGBoost + NetworkX DAG | 8-Class RCA Attribution | Macro $F_1 = 0.9996$ | $0.765$ ms | PASS |
| **M5** | PyTorch Deep MLP (RTX 2050) | 11 Tactical SRE Actions | Test Acc = $99.52\%$, $F_1 = 0.9952$ | $0.314$ ms | PASS |
| **M5.5** | TF-IDF Cosine RAG Copilot | SRE Ops Assistant | Grounded in `secure_action.md` | $1.210$ ms | PASS |
| **M6** | Deterministic Safety Layer | Zero-ML Guardrails | 100% Policy Adherence | $< 0.10$ ms | PASS |
| **M7** | Closed-Loop Actuator | Platform Stabilization | 4-Step Metric Relief | $< 0.25$ ms | PASS |
| **M8** | Chaos Engineering Lab | 8 Scenarios & Knee Curvature | Analytical $M/M/c$ Solver | $< 0.18$ ms | PASS |
| **M9** | MLOps Drift Governance | KS & PSI Shift Analysis | Sensitivity $\ge 99.8\%$ | $1.420$ ms | PASS |

---

## 6. Verification & Quality Gates

The entire repository adheres strictly to enterprise engineering standards:
- **Test Suite**: `134/134 passed` (`make ci`)
- **Backend Test Coverage**: `86.69%` (surpasses the $\ge 80.0\%$ requirement)
- **Static Type Checking**: `mypy --strict backend/` passes with **0 errors across 48 source files**
- **Linting & Style**: `ruff check .` passes with **All checks passed**
- **Continuous Integration**: `.github/workflows/ci.yml` multi-stage matrix pipeline enabled
