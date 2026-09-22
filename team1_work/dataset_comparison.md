# Candidate inspection and comparison

Inspected **7 candidates**. Nothing was cleaned yet at this stage.

Sources used: Hugging Face Hub, Internet Traffic Archive (NASA HTTP), GitHub mirrors (Elastic examples, Loghub).

---

## Per-candidate inspection

### A — University Apache labeled
| | |
|---|---|
| File | `candidates/A_apache_access_labeled.csv` |
| Source | Hugging Face `EgilKarlsen/ApacheAccessLabeled` |
| Format | CSV (parsed log + security label) |
| Rows × cols | 37,693 × 3 |
| Columns | `timestamp`, `log`, `label` |
| What it contains | Real university web access logs for a lecturer-workload system (`/bkd_baru/...`: login, kinerja dosen, pendidikan, penelitian). Labels are **security**: AMAN 29,778 / BAHAYA 4,965 / DICURIGAI 2,950. |
| Time range | 2019-07-01 10:54 → 2019-07-27 08:06 (2,812 unique minutes) |
| Traffic? | **Yes** — HTTP method/path/status/bytes can be parsed from ~81.5% of rows. Requests/min: p50=8, p95=48, max=301. |
| Server metrics? | **No** |
| Performance? | Weak — status codes only, no latency. |
| Possible target? | Security class, **not** capacity. 2,169 duplicate rows. |
| Verdict | Thematically the closest to a college ERP. Cannot train a capacity model by itself. |

### B — Mindweave web-server logs + servers
| | |
|---|---|
| File | `B_mindweave_access_logs.csv` + `B_mindweave_servers.csv` |
| Source | Hugging Face `mindweave/web-server-logs` (free sample) |
| Format | CSV × 2 |
| Rows × cols | Access: 5,000 × 10. Servers: **3 × 4** |
| Access columns | `timestamp`, `server_id`, `method`, `path`, `status_code`, `response_time_ms`, `bytes_sent`, `user_agent`, `ip_address`, `referrer` |
| Server columns | `id`, `name`, `region`, `role` |
| What it contains | Synthetic SaaS HTTP logs with **latency**. The servers file is an **inventory** (3 hosts: api/api/static), **not** CPU/RAM telemetry. A join only adds region/role. |
| Time range | 2024-01-01 → 2024-02-06. Almost 1 request per occupied minute (p50=1, max=3). |
| Traffic? | Very weak — too sparse to form a load curve. |
| Server metrics? | **No** (inventory only). |
| Performance? | **Yes** — `response_time_ms` (median 90 ms, max 7,510 ms) and status codes (85 × 500, 25 × 503). |
| Possible target? | Latency regression on path/method. Not capacity. Latency barely moves with status, so there is no clear degradation-vs-load curve. |
| Verdict | Only public table here with latency. Useless as a standalone PortalPulse dataset. Useful later only as a latency-distribution sanity check. |

### C — WorkloadAnalyzer
| | |
|---|---|
| File | `candidates/C_workload_analyzer.csv` |
| Source | Hugging Face `infinite-dataset-hub/WorkloadAnalyzer` |
| Format | CSV |
| Rows × cols | 98 × 3 |
| Columns | `idx`, `Task Description`, `Labels` |
| What it contains | NLP project-management tasks (“prepare a budget report”). |
| Traffic? | No |
| Server metrics? | No |
| Performance? | No |
| Possible target? | No |
| Verdict | **Reject.** Wrong domain. |

### D — Elastic Apache access logs
| | |
|---|---|
| File | `candidates/D_elastic_apache_logs.txt` |
| Source | GitHub `elastic/examples` (Common Data Formats) |
| Format | Raw Combined Log Format |
| Rows | 10,000 lines, all parseable |
| What it contains | Real website access logs (kibana/logstash demo site). Status mostly 200 (9,126). Only 3 × 500. |
| Time range | 2015-05-17 → 2015-05-20. Only **84** occupied minutes (~120 req/min, almost flat). |
| Traffic? | Yes, but 4 days and nearly constant rate. |
| Server metrics? | No |
| Performance? | Status / bytes only. |
| Possible target? | No capacity target. |
| Verdict | Good parser test. Too short and too flat for capacity learning. |

### E — Loghub Apache 2k
| | |
|---|---|
| File | `candidates/E_loghub_apache_2k.log` |
| Source | GitHub `logpai/loghub` (Apache) |
| Format | Apache **error** log |
| Rows | 2,000 lines |
| What it contains | `[notice]` 1,405 / `[error]` 595 messages (`workerEnv.init`, `mod_jk child ... error state`). **Not an access log.** No GET/POST. |
| Traffic? | **No** |
| Server metrics? | Operational messages only, not CPU/RAM. |
| Performance? | No |
| Possible target? | Log-template / anomaly NLP, not capacity. |
| Verdict | **Reject** for PortalPulse Module 1. |

### F — Elastic Nginx access logs
| | |
|---|---|
| File | `candidates/F_elastic_nginx_logs.txt` |
| Source | GitHub `elastic/examples` |
| Format | Raw Combined Log Format |
| Rows | 51,462 lines, all parseable |
| What it contains | Download-server access log. Status: 33,876 × 404, 13,330 × 304, 4,028 × 200, **0 × 5xx**. The 65.9% “error” rate is missing files, not overload. |
| Time range | 2015-05-17 → 2015-06-04. 432 occupied minutes, ~119 req/min, almost flat. |
| Traffic? | Yes, but flat and 404-dominated. |
| Server metrics? | No |
| Performance? | No latency; errors are content-missing, not saturation. |
| Possible target? | No. |
| Verdict | **Reject** as a capacity source. |

### G — NASA HTTP July 1995
| | |
|---|---|
| File | `candidates/NASA_access_log_Jul95.gz` |
| Source | Internet Traffic Archive (`ita.ee.lbl.gov`) |
| Format | Raw Common Log Format (gzip) |
| Rows | 1,891,715 lines; 1,891,700 parsed |
| What it contains | Real NASA Kennedy Space Center web server traffic for July 1995. Host, timestamp, request, status, bytes. |
| Time range | 28 calendar days. 662 occupied hours. |
| Traffic? | **Best of the seven.** Clear diurnal curve. Requests/hour: min 316, p50 2,448, p95 5,752, max 14,926. Requests/min (early sample): p50 46, max 172. Error rate ~0.58% (mostly 404; only 62 × 500). |
| Hourly shape | Night trough ~32k hits at 04:00; daytime peak ~122k hits at 12:00–14:00 (Eastern). |
| Server metrics? | **No** |
| Performance? | Status + bytes. No latency, CPU, RAM. |
| Possible target? | Can derive load / error-rate time series. **Cannot** label safe capacity from the file alone. |
| Verdict | Strongest **real traffic process**. Selected as the primary demand signal. |

---

## Comparison table

| ID | Dataset | Rows | Format | Useful traffic? | Server metrics? | Performance? | Target possible? |
|---|---|---:|---|---|---|---|---|
| A | University Apache (BKD ERP) | 37,693 | CSV logs + security label | Yes (campus ERP paths) | No | Status only | Security class only |
| B | Mindweave access + servers | 5,000 + 3 | CSV | Too sparse | Inventory, not metrics | Latency + status | Latency, not capacity |
| C | WorkloadAnalyzer | 98 | CSV text | No | No | No | No |
| D | Elastic Apache | 10,000 | Raw access log | Short + flat | No | Status only | No |
| E | Loghub Apache 2k | 2,000 | Error log | No | No | No | No |
| F | Elastic Nginx | 51,462 | Raw access log | Flat, 66% 404s | No | Not overload | No |
| G | NASA HTTP Jul95 | 1,891,715 | Raw access log | **Best real load curve** | No | Status only | Load/errors only |

---

## Selection

**Primary:** NASA HTTP Jul95 (G)
**Secondary:** University Apache labeled (A)

Not chosen as primary despite theme (A) because 2,812 sparse minutes and a security target would force the model to learn “is this request an attack?”, which is the wrong Module 1 question.

Mindweave (B) is **not** selected. `servers.csv` does not contain server metrics; joining it does not create a CPU/RAM dataset.

## Can the selected pair support PortalPulse as-is?

**No.**

PortalPulse needs the relationship:

```
workload  →  CPU / RAM / network / latency / errors  →  safe capacity
```

NASA + University give the left-hand side (real request arrivals, campus ERP paths). They do **not** give server telemetry or a capacity label.

So Team 1 will:

1. Parse G and A into minute-level **real** traffic tables (no invented requests).
2. Use NASA’s real load *shape* as the demand process.
3. Scale that shape to ERP magnitudes (result-day concurrent users).
4. Generate CPU / RAM / network / latency / errors from a documented resource + queueing model driven by that real load.
5. Define `safe_capacity` from SLA on that model, and derive `risk_level`.

This is not “random fake ERP data.” It is **real traffic, modeled server response**, which is the only way to produce a model-ready table from the candidates that actually exist.
