# Week 1 frozen model

Do not retrain these files. They are the Module 1 / Week 1 baseline.

| File | Role |
|---|---|
| `xgboost_safe_capacity.json` | Native XGBoost booster. Dashboard runtime. |
| `xgboost_model.pkl` | sklearn `XGBRegressor` wrapper of the same booster. |
| `xgboost_metadata.json` | Original training MAE / RMSE / R². |
| `feature_list.json` | Locked 11-feature input order. |
| `feature_schema.json` | Same feature list (older name). |
| `model_metrics.json` | Official metrics + time-split evaluation + feature importance. |
| `prediction_test.csv` | Frozen booster scored on `Module1_Data/test.csv`. |

Team 2 write-up: `../team2_work/README.md`.
