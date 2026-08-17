# PortalPulse — Week 1 Dashboard

Streamlit prototype that reads Team 1’s clean dataset and Team 2’s trained XGBoost model, then shows:

1. Dataset health (real row counts, not placeholders)
2. Traffic / load charts from `dataset_clean.csv`
3. Official model metrics (MAE / RMSE / R²)
4. Live simulation: traffic inputs → predicted safe capacity → SAFE / HIGH / OVERLOAD

## Run

From the repo root, with the project venv active:

```bash
source .venv/bin/activate
pip install -r dashboard/requirements.txt
streamlit run dashboard/app.py
```

The app loads:

- `Module1_Data/dataset_clean.csv`
- `team1_work/processed/dataset_raw.csv` (raw vs clean counts)
- `traffic_bot_model/xgboost_safe_capacity.json`
- `traffic_bot_model/xgboost_metadata.json`

## Honest wording

Capacity numbers on this screen are **model-estimated**. They are not a claim about the live IEM result portal.
