# PortalPulse — Week 1 dashboard

Streamlit **Traffic Simulation / AI Prototype**. It reads Team 1’s frozen dataset and Team 2’s frozen XGBoost model.

This is **not** a live traffic monitoring system and is **not** connected to the live IEM portal.

1. **Dataset health** — records, features, target, cleaning
2. **Traffic intelligence** — traffic vs CPU, users vs latency, load by hour, risk distribution
3. **AI model performance** — MAE / RMSE / R², actual vs predicted, feature importance
4. **Traffic simulator**

```
current users
        ↓
estimated safe capacity
        ↓
utilization
        ↓
🟢 SAFE / 🟡 AT RISK / 🔴 OVERLOADED
```

Current users is the input load. Estimated safe capacity is the model output. Utilization is users ÷ capacity. Those are different concepts.

Capacity numbers are a **prototype estimate based on the trained model**.

## Run

From the repo root, with the project venv active:

```bash
source .venv/bin/activate
pip install -r dashboard/requirements.txt
streamlit run dashboard/app.py
```

The app loads:

- `Module1_Data/master_clean.csv`
- `team1_work/processed/dataset_raw.csv`
- `traffic_bot_model/xgboost_safe_capacity.json`
- `traffic_bot_model/xgboost_metadata.json`
- `traffic_bot_model/prediction_test.csv`
