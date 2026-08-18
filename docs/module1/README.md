# Module 1

## Week 1 — frozen baseline

Team 1 cleaned the telemetry. Team 2 trained an XGBoost regressor that estimates **safe concurrent-user capacity**. The dashboard is a **Traffic Simulation / AI Prototype**.

Do not unfreeze Week 1 to add more models. The missing 5–10% was documentation, reproducibility, and a clear baseline — that is now in:

- `Module1_Data/` (data freeze)
- `traffic_bot_model/` and `team2_work/` (model freeze)
- `dashboard/app.py` (four-section prototype)

## Week 2

Week 2 should **not** be “train the model again.”

1. Stress testing and unseen result-day-like conditions
2. Threshold calibration
3. Robustness / generalization
4. Turn the prediction into a traffic-decision mechanism

Optional later comparison work (Linear Regression, Random Forest, LightGBM, ANN / MLP) belongs here only as a comparison against the frozen XGBoost baseline — not as a replacement for it.

```
docs/module1/ANN_MLP/   # planned, not required to close Week 1
├── train_mlp.py
├── mlp_model.pkl
├── scaler.pkl
├── comparison.csv
├── mlp_tuning.ipynb
└── README.md
```
