# Team 2 — Week 1 model freeze

**Status: COMPLETE.** Do not keep retraining randomly. This is the Week 1 baseline.

Official data package (read-only): `../Module1_Data/`
Do **not** edit `../team1_work/` or `../Module1_Data/master_clean.csv`.

## Frozen files

| File | Location |
|---|---|
| `xgboost_model.pkl` | `models/` and `../traffic_bot_model/` |
| `feature_list.json` | `models/` and `../traffic_bot_model/` |
| `model_metrics.json` | `results/` and `../traffic_bot_model/` |
| `prediction_test.csv` | `results/` and `../traffic_bot_model/` |
| `xgboost_safe_capacity.json` | `../traffic_bot_model/` (native booster the dashboard loads) |
| `xgboost_metadata.json` | `../traffic_bot_model/` (original training report) |

Reproduce the freeze (does **not** retrain):

```bash
.venv/bin/python team1_work/scripts/freeze_week1_data.py
.venv/bin/python team2_work/scripts/freeze_week1_model.py
```

The pickle is an `XGBRegressor` wrapper of the already-trained booster. The dashboard continues to load the JSON booster.

---

## Model type

XGBoost **regressor** (`n_estimators=400`, `max_depth=6`, `learning_rate=0.1`, `subsample=0.8`, `colsample_bytree=0.8`).

## Input features (locked order)

```
hour, day_of_week, is_weekend, is_result_window,
concurrent_users, requests_per_sec,
cpu_usage, memory_usage, network_usage,
latency_ms, error_rate
```

## Target

`safe_capacity` — estimated maximum concurrent users before SLA breach.

At inference the dashboard does **not** treat that number as “predicted load”:

```
current users ÷ estimated safe capacity = utilization → SAFE / AT RISK / OVERLOADED
```

---

## Official training metrics

From `xgboost_metadata.json`, recorded when this booster was trained. MAE / RMSE are in concurrent-user units.

| Split | MAE | RMSE | R² |
|---|---|---|---|
| Validation | 147.8 | 190.4 | 0.967 |
| Test | 146.5 | 188.3 | **0.969** |

R² = 0.969 is excellent **on this historical table**. It does not prove the model will work on a real IEM result day. Keep the wording: **prototype estimate based on the trained model**.

## Evaluation on the published time split

Same frozen booster, scored on `Module1_Data/test.csv` (not a new training run):

| Split | MAE | RMSE | R² |
|---|---|---|---|
| Validation (6–8 Jul) | 131.8 | 169.9 | 0.911 |
| Test (9–13 Jul) | 131.3 | 167.3 | 0.913 |

The later days are calmer (few `OVERLOADED` minutes). The drop vs 0.969 is why Week 2 is generalization / stress testing, not “train again.”

Full JSON: `results/model_metrics.json`.

---

## Feature importance (gain share)

| Feature | Share of gain |
|---|---|
| `is_result_window` | 95.1% |
| `hour` | 2.2% |
| `latency_ms` | 0.9% |
| `cpu_usage` | 0.5% |
| `requests_per_sec` | 0.4% |
| `concurrent_users` | 0.3% |
| others | < 0.3% each |

Result-day calendar context dominates remaining capacity. That is expected from how the target was labelled, and it is a reason not to oversell in-sample R².

---

## Week 2 (do not start by retraining)

Build on this baseline:

1. Stress tests and unseen result-day-like conditions
2. Threshold calibration (0.70 / 0.90)
3. Robustness / generalization
4. Turn the prediction into a traffic-decision mechanism

That is when PortalPulse becomes an AI traffic **management** system rather than an ML prediction demo.
