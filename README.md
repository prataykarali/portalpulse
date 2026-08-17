# PortalPulse

AI traffic intelligence for an IEM-style result portal.

Week 1: Team 1 cleaned the dataset, Team 2 trained an XGBoost model that predicts **safe capacity**, and a Streamlit dashboard shows dataset health, traffic, model metrics, and a live simulation.

Open the dashboard at **http://localhost:8501** after the steps below.

---

## Run on a new laptop

You need **Git**, **Python 3.10+**, and a terminal.

### 1. Clone the repo

```bash
git clone https://github.com/prataykarali/portalpulse.git
cd portalpulse
```

### 2. Create and activate a virtual environment

**macOS / Linux**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

**Windows (PowerShell)**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```bash
pip install -r dashboard/requirements.txt
```

That installs Streamlit, pandas, numpy, plotly, and xgboost.

### 4. Start the dashboard

From the **repo root** (`portalpulse/`):

```bash
streamlit run dashboard/app.py
```

The app starts on **port 8501**.

- Local: [http://localhost:8501](http://localhost:8501)
- Same machine: [http://127.0.0.1:8501](http://127.0.0.1:8501)

If the browser does not open by itself, paste that URL in.

Stop the server with `Ctrl+C`.

### 5. (Optional) Use a different port

```bash
streamlit run dashboard/app.py --server.port 8502
```

Then open `http://localhost:8502`.

---

## What you should see

1. **Dataset health** — real counts from the clean CSV (39,584 records, 11 features, target `safe_capacity`).
2. **Traffic / load** — users, CPU, latency, and the stress knee.
3. **Model performance** — XGBoost test MAE / RMSE / R² and actual vs predicted.
4. **Live simulation** — sliders or presets → predicted load % → SAFE / HIGH / OVERLOAD.

Capacity numbers are **model estimates** from the trained booster and this dataset. They are not a live reading of the IEM portal.

---

## Repo layout

```
portalpulse/
├── Module1_Data/              Team 1 handoff (clean CSV + docs)
│   └── dataset_clean.csv
├── team1_work/                Team 1 research / cleaning log
├── team2_work/                Team 2 working folder
├── traffic_bot_model/         Trained XGBoost + metrics
│   ├── xgboost_safe_capacity.json
│   ├── xgboost_metadata.json
│   └── feature_schema.json
├── dashboard/
│   ├── app.py                 Streamlit app
│   ├── requirements.txt
│   └── .streamlit/config.toml
└── README.md                  this file
```

The dashboard reads:

- `Module1_Data/dataset_clean.csv`
- `team1_work/processed/dataset_raw.csv` (raw vs clean counts)
- `traffic_bot_model/xgboost_safe_capacity.json`
- `traffic_bot_model/xgboost_metadata.json`

Do **not** edit `Module1_Data/dataset_clean.csv`. It is the source of truth.

---

## Quick checks if something fails

| Problem | Fix |
|---|---|
| `streamlit: command not found` | Activate `.venv`, then `pip install -r dashboard/requirements.txt` |
| App says files are missing | Run `streamlit run dashboard/app.py` from the **repo root**, not from `dashboard/` |
| Port 8501 already in use | `streamlit run dashboard/app.py --server.port 8502` |
| Charts empty / model error | Confirm `traffic_bot_model/xgboost_safe_capacity.json` is present after clone |

Verify the dataset after clone:

```bash
python -c "import pandas as pd; df=pd.read_csv('Module1_Data/dataset_clean.csv'); print(df.shape)"
```

Expected: `(39584, 14)`.

---

## Module 1 notes

| Folder | Role |
|---|---|
| `Module1_Data/` | Official clean dataset. Read-only. |
| `team1_work/` | Team 1 research. Do not edit. |
| `traffic_bot_model/` | Team 2 trained model used by the dashboard. |
| `team2_work/` | Team 2 scratch / experiments. |
| `dashboard/` | Week 1 Streamlit prototype. |

Team 1 docs: `Module1_Data/README.md`, `data_dictionary.md`, `feature_notes.md`.  
Team 2 notes: `team2_work/README.md`.
