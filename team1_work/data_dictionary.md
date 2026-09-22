# Data dictionary

Master table: `processed/dataset_clean.csv`
Grain: **one row = one minute** of the ERP-like system.
Rows: 39,584 after cleaning. Columns: 14.

| Column | Meaning | Type | Role | Allowed values / notes |
|---|---|---|---|---|
| `timestamp` | Start of the 1-minute window (naive local clock on the 2025 academic observation window) | datetime | index / time feature | 2025-06-16 00:00 → 2025-07-13 13:32 |
| `hour` | Hour of day extracted from `timestamp` | integer | feature | 0–23 |
| `day_of_week` | Monday=0 … Sunday=6 | integer | feature | 0–6 |
| `is_weekend` | 1 if Saturday or Sunday | integer (flag) | feature | 0 or 1 |
| `is_result_window` | 1 if this minute falls on a known heavy “result / announcement” day | integer (flag) | feature | 0 or 1. Legitimate calendar feature — result dates are known in advance. |
| `concurrent_users` | Active users in the minute | integer | feature | 56–12,500. Scaled from NASA unique hosts; rank order of the real load is preserved. |
| `requests_per_sec` | HTTP arrival rate | float | feature | ≈ 5.6–1,769. Mixture of host-implied and request-implied NASA intensity. |
| `cpu_usage` | CPU utilization | float (%) | feature | 0–100 |
| `memory_usage` | RAM utilization | float (%) | feature | 0–100 |
| `network_usage` | Network utilization | float (%) | feature | 0–100 |
| `latency_ms` | Mean response time in the minute | float (ms) | feature | ≥ 15. SLA line used for the target is **800 ms**. |
| `error_rate` | Fraction of failed requests in the minute | float | feature | 0–1. SLA line used for the target is **0.01**. |
| `safe_capacity` | Maximum concurrent users the system can still serve without breaching SLA, given current hidden headroom | integer | **primary target** | 3,626–9,248. Regression target. |
| `risk_level` | Operating-risk class derived from utilization and live SLA breach | string | **derived target** | `SAFE` / `AT_RISK` / `OVERLOADED` |

## Target definitions (locked after EDA)

### Option A — `safe_capacity` (regression)

> Given current traffic and server telemetry, how many concurrent users can the system handle before SLA breach?

SLA used to label the target (not features):

- latency < 800 ms
- error rate < 1%
- CPU < 85%

`safe_capacity` is the largest user count that still satisfies all three, given the minute’s hidden headroom (background CPU/RAM and query weight). Those hidden variables are **not** in this table. The model has to infer remaining headroom from the observables.

### Option B — `risk_level` (classification), derived from A

Let `utilization = concurrent_users / safe_capacity`.

| Class | Rule |
|---|---|
| `SAFE` | utilization < 0.70 and no live SLA breach |
| `AT_RISK` | 0.70 ≤ utilization < 0.90 and no live SLA breach |
| `OVERLOADED` | utilization ≥ 0.90 **or** latency/error/CPU already past SLA |

Class counts in the clean table: SAFE 33,294 · AT_RISK 3,156 · OVERLOADED 3,134.

## What is *not* in this table

- No train / validation / test split. Team 2 splits.
- No `utilization` column. Computing `concurrent_users / safe_capacity` and using it as a feature **is leakage**.
- No hidden-state columns (`query_weight`, background jobs).
- No raw HTTP paths, IPs, or user agents. Those live in the selected traces if Team 2 ever wants them.

## Units cheat-sheet

| Quantity | Unit |
|---|---|
| users / capacity | count |
| requests_per_sec | requests / second |
| cpu / memory / network | percent of that resource |
| latency | milliseconds |
| error_rate | fraction (0.01 = 1%) |
