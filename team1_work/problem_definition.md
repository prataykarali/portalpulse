# Problem definition (locked before cleaning)

## What PortalPulse is predicting

Predict the **safe operating capacity** of a web/ERP system under varying traffic and server conditions.

Typical ERP failure mode: result-day (or registration-day) traffic arrives much faster than the application/database tier can serve it. CPU and RAM climb, latency bends upward, then errors spike. The system is already late by the time a human sees a red dashboard.

## What the model should learn

Given **current traffic + server telemetry**, estimate:

- **Option A (primary target):** `safe_capacity` — approximately how many concurrent users the system can still handle before SLA breach.
- **Option B (derived target):** `risk_level` — `SAFE` / `AT_RISK` / `OVERLOADED`, derived from utilization = current users / safe capacity.

Example output later modules can consume:

> Current users: 8,000 → estimated safe capacity: 10,500 → 76% utilization → SAFE.

## Candidate features (not locked until the dataset is seen)

| Candidate | Why it matters |
|---|---|
| Concurrent users | Direct workload |
| Requests/sec | Arrival intensity |
| CPU utilization | Compute saturation |
| RAM utilization | Memory pressure / paging |
| Latency | User-visible degradation |
| Error rate | Hard failure signal |
| Network utilization | Bandwidth saturation |
| Time of day / calendar | Result windows, office hours |

## What we will **not** lock yet

The target is **not** permanently locked to a column we have not seen. If a candidate only supports security labels, or only HTTP status codes, we will not pretend it is a capacity dataset.

## Success condition for Team 1

A single master table `dataset_clean.csv` that:

1. Represents workload ↔ performance (not just raw logs).
2. Has an explicit, justified target.
3. Is **not** pre-split into train/val/test.
4. Is documented well enough that Team 2 can split, preprocess, and train without guessing.
