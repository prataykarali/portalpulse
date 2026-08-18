# Team 1 — Week 1 data freeze

**Status: COMPLETE.** Do not reclean or reshuffle these files.

This folder is the official Week 1 data package. The research log lives in `../team1_work/`.

## Frozen files

| File | What it is |
|---|---|
| `master_clean.csv` | Master table. 39,584 rows × 14 columns. Same bytes as `dataset_clean.csv`. |
| `data_dictionary.csv` | Column meanings, types, roles. |
| `train.csv` | Time-split train set (28,720 rows). |
| `validation.csv` | Time-split validation set (4,305 rows). |
| `test.csv` | Time-split test set (6,559 rows). |
| `split_manifest.json` | Split rule, row counts, SHA-256 hashes. |
| `dataset_clean.csv` | Original handoff name. Keep; dashboard falls back to it. |

Reproduce the freeze (does **not** reclean the data):

```bash
.venv/bin/python team1_work/scripts/freeze_week1_data.py
```

---

## What each feature means

Grain: **one row = one minute**.

| Column | Role | Meaning |
|---|---|---|
| `timestamp` | index | Start of the minute. 2025-06-16 00:00 → 2025-07-13 13:32. Not a model input. |
| `hour` | feature | Hour of day, 0–23. |
| `day_of_week` | feature | Monday=0 … Sunday=6. |
| `is_weekend` | feature | 1 if Saturday or Sunday. |
| `is_result_window` | feature | 1 on a known result / announcement day. Calendar feature, not leakage. |
| `concurrent_users` | feature | Active users in the minute (56–12,500). |
| `requests_per_sec` | feature | HTTP arrival rate. |
| `cpu_usage` | feature | CPU utilization, 0–100%. |
| `memory_usage` | feature | RAM utilization, 0–100%. |
| `network_usage` | feature | Network utilization, 0–100%. |
| `latency_ms` | feature | Mean response time (ms). SLA line = 800 ms. |
| `error_rate` | feature | Fraction of failed requests. SLA line = 0.01. |
| `safe_capacity` | **target** | See below. |
| `risk_level` | derived | `SAFE` / `AT_RISK` / `OVERLOADED`. |

Full notes: `data_dictionary.csv`, `data_dictionary.md`, `feature_notes.md`.

---

## What `safe_capacity` means

`safe_capacity` is the **maximum concurrent users** the system can still serve without breaching SLA, given that minute’s hidden headroom.

SLA used to **label** the target (not as extra features):

- latency < 800 ms
- error rate < 1%
- CPU < 85%

This is **not** the same thing as current load.

```
current users          ← traffic snapshot (input)
        ↓
estimated safe capacity ← model output
        ↓
utilization = current users ÷ estimated safe capacity
        ↓
SAFE / AT RISK / OVERLOADED
```

Do **not** feed `utilization = concurrent_users / safe_capacity` back in as a feature. That is leakage.

---

## How cleaning was performed

Applied only after source selection and target definition. Log: `../team1_work/processed/cleaning_log.md`.

| Step | Rows |
|---|---|
| Raw table | 39,711 |
| Duplicate rows removed | 18 |
| Impossible sensor rows (`cpu_usage = 999`, negative latency) | 10 |
| Monitoring dropouts (missing CPU/RAM) | 99 |
| **Clean master** | **39,584** |

Also: dropped an internal id column, clipped percents to [0, 100], clipped rates to valid ranges, fixed dtypes, sorted by timestamp.

We did **not** drop high-latency result-day minutes. Those are the knee, not noise.

Missing values in the clean table: 0. Duplicates: 0.

---

## Date / time range

- Start: **2025-06-16 00:00**
- End: **2025-07-13 13:32**
- Calendar days: **28**
- Grain: one minute

Demand *shape* is real NASA HTTP traffic (July 1995), scaled to ERP-like user counts and remapped onto this 2025 academic window. CPU / RAM / latency / errors / `safe_capacity` come from a documented resource model — **not** a live IEM dump.

---

## Train / validation / test split

Time split, as recommended in `feature_notes.md`:

| Split | Rule | Rows | Window |
|---|---|---|---|
| Train | `timestamp < 2025-07-06` | 28,720 | 16 Jun → 5 Jul |
| Validation | 3 days before test | 4,305 | 6 Jul → 8 Jul |
| Test | last 5 calendar days | 6,559 | 9 Jul → 13 Jul 13:32 |

Hashes are in `split_manifest.json`.

The original XGBoost training-row split was not checked in with the booster. This published time split is the **Week 1 freeze** so nobody retrains on a random shuffle.

---

## Honesty

This is **not** a production IEM portal dump. It is the Week 1 baseline table Team 2 trained on, and the table the dashboard reads.
