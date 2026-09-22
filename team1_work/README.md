# Team 1 — Module 1 data work

**Week 1 deliverable: COMPLETE.** Official freeze is `../Module1_Data/` (`master_clean.csv`, `data_dictionary.csv`, `train.csv`, `validation.csv`, `test.csv`). Do not reclean the master table.

This folder is Team 1’s working directory / research log.
**Team 2 should take the package in `../Module1_Data/`**, not this whole tree.

---

## Problem

Predict the **safe operating capacity** of a web / ERP system under varying traffic and server conditions.

Typical failure: result-day traffic arrives faster than the app/DB tier can serve it. CPU and RAM climb, latency bends up, then errors spike.

We locked two targets after seeing the data (not before):

- **A (primary):** `safe_capacity` — how many concurrent users the system can still handle.
- **B (derived):** `risk_level` — `SAFE` / `AT_RISK` / `OVERLOADED`.

See `problem_definition.md` and `data_dictionary.md`.

---

## What we did, in order

```
7 candidate datasets
        ↓
   inspect each
        ↓
   comparison table   →  dataset_comparison.md
        ↓
   pick NASA (G) + University Apache (A)
        ↓
   deep inspect: can they support PortalPulse as-is?
        ↓
   NO — traffic yes, CPU/RAM/capacity label no
        ↓
   parse selected traces to minute tables
        ↓
   real NASA load shape + documented resource model
        ↓
   clean (one master file, no splits)
        ↓
   EDA
        ↓
   handoff
```

We did **not** start by cleaning every candidate.
We did **not** emit `train.csv` / `val.csv` / `test.csv`.

---

## Source: what we downloaded

| ID | File | Source | Why we looked at it |
|---|---|---|---|
| A | `candidates/A_apache_access_labeled.csv` | Hugging Face `EgilKarlsen/ApacheAccessLabeled` | Real university ERP-like traffic (`/bkd_baru/`, lecturer workload). Security labels, not capacity. |
| B | `B_mindweave_access_logs.csv` + `B_mindweave_servers.csv` | Hugging Face `mindweave/web-server-logs` | Only table with latency. `servers.csv` is a 3-row **inventory**, not CPU/RAM. Too sparse. |
| C | `C_workload_analyzer.csv` | Hugging Face `infinite-dataset-hub/WorkloadAnalyzer` | NLP project tasks. Rejected. |
| D | `D_elastic_apache_logs.txt` | GitHub `elastic/examples` | Real access log, 4 days, almost flat. |
| E | `E_loghub_apache_2k.log` | GitHub `logpai/loghub` | Apache **error** log, not access. Rejected. |
| F | `F_elastic_nginx_logs.txt` | GitHub `elastic/examples` | 66% HTTP 404s (missing files), 0 × 5xx. Rejected. |
| G | `NASA_access_log_Jul95.gz` | Internet Traffic Archive | 1.89M real NASA web requests, 28 days, clear diurnal curve. **Selected.** |

Full column-level inspection: `dataset_comparison.md`.

### Selected

- **Primary:** NASA HTTP July 1995 — best real load process.
- **Secondary:** University Apache (A) — only ERP-like campus application; used for theme + burstiness (CV), not as the request clock.

Copies of the selected originals and the parsed minute tables live in `selected/`.

---

## Can the selected pair support PortalPulse as-is?

**No.** Neither file has CPU, RAM, network, or a capacity label.

Public traces we could actually download split into two families:

1. HTTP access logs (traffic, sometimes status/bytes, rarely latency).
2. Datacenter VM traces (CPU/RAM, no HTTP users).

Nothing in the seven-candidate set joins those families.

So the master table is:

**real NASA request intensity (rank-preserving, scaled to ERP user counts)**
→ documented M/M/c + resource model
→ CPU, RAM, network, latency, errors
→ `safe_capacity` from SLA, `risk_level` from utilization.

This is **not** a production ERP dump and we do not claim it is. It is the only honest way to give Team 2 a table that actually contains the relationship Module 1 needs to learn.

Reproduce:

```bash
.venv/bin/python team1_work/scripts/parse_selected.py
.venv/bin/python team1_work/scripts/build_dataset.py
.venv/bin/python team1_work/scripts/build_eda.py
```

---

## Cleaning: what we changed

Applied only after selection and target definition. Full list: `processed/cleaning_log.md`.

- Dropped an irrelevant internal id column.
- Removed 18 duplicate rows.
- Removed 10 impossible sensor rows (`cpu_usage = 999`, negative latency).
- Removed 99 rows with missing CPU/RAM (injected monitoring dropouts).
- Clipped percents to [0, 100] and rates to valid ranges.
- Fixed dtypes and sorted by timestamp.

Final clean table: **39,584 rows × 14 columns**, 0 missing, 0 duplicates.

We did **not** drop high-latency result-day minutes. Those are the knee, not noise.

---

## Features: what the model receives

```
hour, day_of_week, is_weekend, is_result_window,
concurrent_users, requests_per_sec,
cpu_usage, memory_usage, network_usage,
latency_ms, error_rate
```

Details: `feature_notes.md`.

---

## Target: what the model predicts

| Column | Task | Meaning |
|---|---|---|
| `safe_capacity` | regression | max safe concurrent users under SLA (800 ms / 1% errors / 85% CPU) |
| `risk_level` | classification | `SAFE` (<70% util) / `AT_RISK` (70–90%) / `OVERLOADED` (≥90% or already breaching) |

Class mix: SAFE 33,294 · AT_RISK 3,156 · OVERLOADED 3,134.

---

## Known limitations

1. Server telemetry and the target are **modelled**, not scraped from a college ERP. Demand *shape* is real (NASA). Response *surface* is a queueing/resource model.
2. NASA is a 1995 public website, not a 2025 result portal. We scale magnitude and remap timestamps onto a 2025 academic window; we do not invent extra request spikes beyond NASA’s own heaviest days.
3. University log A is thematically right (BKD / lecturer ERP) but too sparse and security-labeled to be the demand clock.
4. `servers.csv` in candidate B does **not** contain server metrics. Joining it would not have created CPU/RAM.
5. Classes are imbalanced. Accuracy is the wrong headline metric for Option B.
6. `concurrent_users` and `requests_per_sec` are collinear. Linear models need regularization or a choice of one.
7. No production IDs, campuses, or student PII.

---

## Folder

```
team1_work/
├── candidates/              # all 7 downloads, untouched
├── selected/                # NASA + University originals + minute tables
├── processed/
│   ├── dataset_raw.csv      # before cleaning (Team 1 only)
│   ├── dataset_clean.csv    # master table
│   └── cleaning_log.md
├── EDA/
│   └── EDA.ipynb
├── scripts/
├── dataset_comparison.md
├── problem_definition.md
├── data_dictionary.md
├── feature_notes.md
└── README.md                # this file
```

Team 2 package (`../Module1_Data/`):

```
dataset_clean.csv
data_dictionary.md
EDA.ipynb
feature_notes.md
README.md
```
