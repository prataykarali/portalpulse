# Module 1 — ANN / MLP & Full Pipeline

This folder contains the **planned** ANN / MLP work for Module 1 (not yet executed in the repo).

## What was planned (Module 1 TODO)

Team 2 was supposed to:

1. Linear Regression baseline
2. Random Forest
3. XGBoost (already done)
4. LightGBM
5. **ANN / MLP** (Neural Network)
6. Model comparison + tuning
7. Final test + stress test

The official metrics folder now contains:

- `xgboost_metadata.json` (done)
- `xgboost_safe_capacity.json` (done)

## Future work (Module 1 ANN/MLP)

After the XGBoost model is saved, add a folder like:

```
module1/ANN_MLP/
├── train_mlp.py
├── mlp_model.pkl          # or .h5
├── scaler.pkl
├── comparison.csv
├── mlp_tuning.ipynb
└── README.md
```

## Current status

- XGBoost is complete and used in the Week 1 dashboard.
- ANN / MLP are **planned** but not shipped yet.

Add them when you finish the full pipeline and the folder will be pushed automatically.
