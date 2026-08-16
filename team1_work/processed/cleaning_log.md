# Cleaning log

Applied only after selection and target definition.

- Dropped irrelevant column `scratch_trace_id` (internal trace id, not a feature).
- Removed 18 duplicate rows (39711 → 39693).
- Removed 10 impossible sensor rows (cpu_usage>100 or latency_ms<0).
- Removed 99 rows with missing CPU/RAM (monitoring dropouts, 0.25% of remaining).
- Clipped cpu/memory/network to [0, 100], error_rate to [0, 1], users/rps to ≥ 0.
- Fixed dtypes: timestamps datetime, flags/ints, risk_level string.
- Sorted by timestamp. Final shape: 39584 rows × 14 columns.

## Build stats
- NASA occupied minutes: 39531
- Full reindexed minutes: 39693
- University occupied minutes: 2812
- University request CV (burstiness used as a small mixer): 1.289
- NASA unique_hosts p50/p99: 15.0 / 50.0
- Result-window minutes: 4320
- Risk counts (pre-clean prototype): {'SAFE': 33379, 'AT_RISK': 3169, 'OVERLOADED': 3145}
- Users p50/max: 2583 / 12500
- safe_capacity p50: 7230
- Latency p50/p95: 58.2 / 241.7 ms

Team 2 must split `dataset_clean.csv` themselves. No train/val/test files are produced here.
