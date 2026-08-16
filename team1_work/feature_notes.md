# Feature notes for Team 2

## Recommended feature set

Use these as **X**:

```
hour
day_of_week
is_weekend
is_result_window
concurrent_users
requests_per_sec
cpu_usage
memory_usage
network_usage
latency_ms
error_rate
```

Primary **y**: `safe_capacity`  
Optional second **y**: `risk_level`

Leave `timestamp` out of the model matrix (use it only to do a time-based split).

## Why each feature is here

| Feature | Why it belongs |
|---|---|
| `concurrent_users` | Direct workload. The product question is “how many users can we take?” |
| `requests_per_sec` | Arrival intensity. Two minutes with the same user count can have different think-times / request mix. |
| `cpu_usage` | Strongest saturation signal. Tracks users tightly until the knee. |
| `memory_usage` | Softer constraint. Moves less than CPU; still needed so the model can see RAM-bound minutes. |
| `network_usage` | Bandwidth pressure; rises with RPS and heavier result-day payloads. |
| `latency_ms` | User-visible degradation. Relationship vs users is **nonlinear** (flat, then a knee). |
| `error_rate` | Hard-failure signal. Stays near zero until overload, then jumps. |
| `hour`, `day_of_week`, `is_weekend` | NASA’s real diurnal / weekly shape. Night vs afternoon is not the same operating point. |
| `is_result_window` | Known calendar event. Result-day queries are heavier, so capacity drops even at similar user counts. This is **not** leakage. |

## Derived features Team 2 may add (after the split)

Justified, if they want them, and only computed inside each fold:

- `cpu_per_user = cpu_usage / concurrent_users`
- `latency_log = log1p(latency_ms)`
- `is_business_hour = hour between 9 and 17`
- cyclic time: `sin(2π hour/24)`, `cos(2π hour/24)`

Do **not** add:

- `utilization = concurrent_users / safe_capacity`
- anything built from `safe_capacity` or `risk_level` if that column is the target
- future-looking rolling stats that use minutes after the prediction time (time leakage)

## Multicollinearity

`concurrent_users` and `requests_per_sec` are two views of the same demand. Linear models will be unstable if both are used unregularized. Trees / MLP can keep both.

Pearson correlation understates the value of `latency_ms` and `error_rate` because of the knee. Prefer plots and tree importances over a correlation table when deciding to drop them.

## Target advice

The product wants both numbers and a status:

> current users 8,000 → safe capacity 10,500 → 76% → SAFE

So the cleanest Team 2 pipeline is:

1. Predict `safe_capacity` (regression: MAE, RMSE).
2. At inference, compute `utilization = current_users / predicted_capacity`.
3. Map utilization to `SAFE` / `AT_RISK` / `OVERLOADED` with the same 0.70 / 0.90 cuts.

Training a classifier on `risk_level` is a useful **baseline / comparison**, not a replacement. The class is imbalanced (~84 / 8 / 8). Accuracy will look great if the model always says SAFE. Report macro-F1 and recall on `OVERLOADED`.

The costly error is a **false negative**: OVERLOADED predicted as SAFE.

## Split advice (Team 2 owns this)

Preferred: **time split** (e.g. last 5 calendar days = test, the 3 days before that = validation).  
Acceptable: stratified random split on `risk_level` if they want more overloaded minutes in the test set.

Fit scalers on train only. Do not ask Team 1 to re-export splits if a transform changes.
