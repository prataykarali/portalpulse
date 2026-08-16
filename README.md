# PortalPulse

College ERP traffic / capacity project.

## Module 1 status — Team 1 data work is done

Team 2 starts from **`Module1_Data/`**. They do **not** need to go back through the candidate datasets unless they discover a problem with the data.

| File | What it is |
|---|---|
| `dataset_clean.csv` | One clean master table (no train/val/test split) |
| `data_dictionary.md` | Columns, units, target rules |
| `EDA.ipynb` | Distributions, correlations, degradation knee |
| `feature_notes.md` | Features, leakage, split advice |
| `README.md` | Handoff in one page |

**Folder roles (keep this distinction explicit):**

- `team1_work/` = Team 1 working / research area. **Do not edit.**
- `Module1_Data/` = official handoff package. **Read-only for Team 2.**
- `team2_work/` = everything Team 2 produces.

Team 1 working notes, raw candidates, parsers, and the cleaning log live in `team1_work/`.

---

## Setup

```bash
git clone https://github.com/prataykarali/portalpulse.git
cd portalpulse

python3 -m venv .venv
source .venv/bin/activate
pip install pandas numpy matplotlib seaborn scikit-learn jupyter

# verify the master table
python3 -c "import pandas as pd; df=pd.read_csv('Module1_Data/dataset_clean.csv'); print(df.shape); print(df.columns.tolist())"

# open Team 1 EDA
jupyter notebook Module1_Data/EDA.ipynb
```

Do **not** modify `Module1_Data/dataset_clean.csv`. It is the source of truth.

---

## TEAM 2 — What they do now

Their job is now:

**Turn `dataset_clean.csv` into a trained, evaluated, locally runnable PortalPulse model.**

Create a completely separate folder:

```
PORTALPULSE/
│
├── Module1_Data/          ← TEAM 1 (read-only)
│   ├── dataset_clean.csv
│   ├── data_dictionary.md
│   ├── EDA.ipynb
│   ├── feature_notes.md
│   └── README.md
│
├── team1_work/            ← TEAM 1 (do not edit)
│   └── ...
│
└── team2_work/            ← TEAM 2
    ├── experiments/
    ├── models/
    ├── notebooks/
    ├── scripts/
    ├── results/
    └── README.md
```

### Step 1 — Understand the dataset

First open:

- `Module1_Data/dataset_clean.csv`
- `Module1_Data/data_dictionary.md`
- `Module1_Data/feature_notes.md`

Answer:

- What are X?
- What is y?
- How many rows?
- How many features?
- Are there missing values?
- What is the target distribution?

**Do not modify the master dataset.**

### Step 2 — Build the ML preprocessing pipeline

```
dataset_clean.csv
       ↓
select X and y
       ↓
train / validation / test split
       ↓
preprocessing
```

If scaling is necessary:

```
TRAIN
 ↓
fit scaler
 ↓
transform train

VALIDATION
 ↓
transform using TRAIN scaler

TEST
 ↓
transform using TRAIN scaler
```

This is Team 2’s responsibility. Fit any scaler on **train only**.

### Step 3 — Create the train / validation / test sets

```
team2_work/
└── data/
    ├── train.csv
    ├── validation.csv
    └── test.csv
```

These are generated experiment artifacts, **not** replacements for the clean master dataset.

`Module1_Data/dataset_clean.csv` remains the source of truth.

Preferred split: **time split** (see `feature_notes.md`). Stratified random split on `risk_level` is acceptable.

### Step 4 — Train the baseline

First model: **Linear Regression**

Why? Team 2 needs to know: *can a very simple model already solve this reasonably well?*

Record:

- MAE
- RMSE
- R²

### Step 5 — Train the candidate models

Then:

- Random Forest
- XGBoost
- LightGBM
- MLP / ANN

Experiments folder might become:

```
experiments/
├── 01_linear_regression.ipynb
├── 02_random_forest.ipynb
├── 03_xgboost.ipynb
├── 04_lightgbm.ipynb
└── 05_mlp.ipynb
```

Or, preferably, consolidate into a reusable training script rather than five disconnected notebooks.

### Step 6 — Compare them

Create:

```
results/
└── model_comparison.csv
```

| Model | MAE | RMSE | R² |
|---|---|---|---|
| Linear Regression | — | — | — |
| Random Forest | — | — | — |
| XGBoost | — | — | — |
| LightGBM | — | — | — |
| MLP | — | — | — |

Those numbers must come from the actual experiment.

### Step 7 — Investigate the top models

Suppose XGBoost → #1, LightGBM → #2, Random Forest → #3.

Do **not** immediately declare XGBoost the winner.

Investigate:

- overfitting
- validation performance
- large errors
- high-load performance
- prediction behavior
- inference time

### Step 8 — Tune the top 2–3

For example: XGBoost, LightGBM, Random Forest.

Run **controlled** hyperparameter tuning.

Not: “Let’s try 50,000 combinations.”

Just enough to determine whether tuning materially improves performance.

### Step 9 — Final untouched test

After the model is finalized:

```
             TEST SET
                ↓
        FINAL MODEL
                ↓
       Final MAE / RMSE / R²
```

Those become the official Module 1 metrics.

### Step 10 — Stress test PortalPulse’s important region

This is especially important.

Test the model around the region where the system starts becoming unhealthy:

```
Normal traffic
      ↓
Increasing traffic
      ↓
Warning zone
      ↓
Critical / overload zone
```

The question is not merely “does the model have a good R²?”

It is: **does it make useful predictions where PortalPulse actually needs to make decisions?**

### Step 11 — Save the winning model

Final Team 2 folder should look roughly like:

```
team2_work/
│
├── data/
│   ├── train.csv
│   ├── validation.csv
│   └── test.csv
│
├── scripts/
│   ├── preprocess.py
│   ├── train.py
│   └── evaluate.py
│
├── experiments/
│   └── ...
│
├── results/
│   ├── model_comparison.csv
│   └── final_metrics.json
│
├── models/
│   ├── final_model.pkl
│   └── preprocessing.pkl
│
└── README.md
```

---

## Handoff between the two teams

```
YOU (Team 1)
Raw datasets
     ↓
Dataset selection
     ↓
Cleaning
     ↓
EDA
     ↓
Feature / target definition
     ↓
📦 dataset_clean.csv

TEAM 2
📦 dataset_clean.csv
     ↓
X / y
     ↓
Train / Val / Test
     ↓
Preprocessing
     ↓
Linear Regression
Random Forest
XGBoost
LightGBM
MLP
     ↓
Comparison
     ↓
Tuning
     ↓
Final testing
     ↓
🏆 Best model
     ↓
Local model package
```

If Team 2 experiments with five models, breaks something, or changes preprocessing, the clean dataset stays untouched.

---

## Team 2 first three tasks (start now)

1. Read `Module1_Data/data_dictionary.md` + `feature_notes.md`.
2. Load `dataset_clean.csv` and verify X / y.
3. Build the train / validation / test + preprocessing pipeline.

After that, model training begins.

---

## Week 1 milestone (both teams)

The goal is **not** “we just trained a model.”

The goal is a working ML baseline / prototype and enough evidence that the idea is technically viable:

```
                DATASET
                   ↓
              PREPROCESS
                   ↓
             TRAINED MODEL
                   ↓
             NEW INPUT DATA
                   ↓
              PREDICTION
                   ↓
       "Safe capacity ≈ 9,400"
```

A small Week 1 dashboard / demo is recommended. **Not** the final PortalPulse dashboard — just a proof-of-concept:

- Input: concurrent users, CPU, RAM, latency, error rate
- Output: predicted safe capacity + risk status (`SAFE` / `AT_RISK` / `OVERLOADED`)
- Show model name + MAE / RMSE / R²
- One small plot (users vs latency, or traffic vs predicted capacity)

Do **not** build in Week 1: Kubernetes, auto-scaling, Qwen/SLM, login, production DB, cloud deploy, or the full final UI.

Recommended extra folder when the model exists:

```
week1_demo/
├── app.py
├── model/
└── README.md
```

**Week 1 success:** PortalPulse can take server / traffic data, run it through a trained ML model locally, and produce a meaningful capacity prediction.
