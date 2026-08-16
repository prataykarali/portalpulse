"""Build the model-ready master table from the selected traces.

Demand (users, rps) comes from the real NASA minute-level load shape.
Server telemetry and the target come from a documented resource + M/M/c
model driven by that load. Nothing is train/val/test split here.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SEL = ROOT / "team1_work" / "selected"
PROC = ROOT / "team1_work" / "processed"

SEED = 42

# SLA used to define capacity (documented, not fitted)
SLA_LATENCY_MS = 800.0
SLA_ERROR_RATE = 0.01
SLA_CPU = 85.0
SAFE_UTIL = 0.70
RISK_UTIL = 0.90

# Hardware / service model (sized so p50 NASA load is SAFE and only real peaks kneel)
N_WORKERS = 40.0
BASE_SERVICE_MS = 30.0
CPU_PER_RPS = 0.068
RAM_BASE = 22.0
RAM_PER_USER = 0.0036
NET_PER_RPS = 0.042
THINK_TIME_S = 7.0  # used only to express capacity in users

# ERP magnitude: NASA unique_hosts and requests are scaled, shape is kept
TARGET_P50_USERS = 2600.0
TARGET_PEAK_USERS = 12500.0


def _risk_from_util(util: np.ndarray, sla_breach: np.ndarray) -> np.ndarray:
    risk = np.where(util >= RISK_UTIL, "OVERLOADED", np.where(util >= SAFE_UTIL, "AT_RISK", "SAFE"))
    risk = np.where(sla_breach, "OVERLOADED", risk)
    return risk


def _telemetry(users, rps, query_weight, bg_cpu, bg_ram, rng):
    """Map load + hidden headroom → observed server metrics."""
    cpu = bg_cpu + CPU_PER_RPS * rps * query_weight
    cpu = np.clip(cpu + rng.normal(0, 1.15, size=len(cpu)), 0, 100)

    memory = bg_ram + RAM_PER_USER * users * (0.85 + 0.15 * query_weight)
    memory = np.clip(memory + rng.normal(0, 0.9, size=len(memory)), 0, 100)

    network = np.clip(NET_PER_RPS * rps * (0.7 + 0.3 * query_weight) + rng.normal(0, 1.2, size=len(rps)), 0, 100)

    n_eff = N_WORKERS * np.clip(1.0 - bg_cpu / 100.0, 0.15, 1.0)
    service_s = (BASE_SERVICE_MS * query_weight) / 1000.0
    rho = (rps * service_s) / n_eff
    rho_c = np.clip(rho, 0, 0.992)
    # M/M/c-style wait: service / (1-rho) plus a small network term
    latency = (service_s / (1.0 - rho_c)) * 1000.0 + 8.0 + 0.35 * network
    # extra collapse once the system is past the knee
    latency = latency + np.maximum(0.0, rho - 0.88) * 4200.0
    latency = np.clip(latency + rng.normal(0, 12.0, size=len(latency)), 15, 8000)

    err_lat = 1.0 / (1.0 + np.exp(-(latency - 1400.0) / 180.0))
    err_cpu = 1.0 / (1.0 + np.exp(-(cpu - 93.0) / 2.4))
    err_rho = 1.0 / (1.0 + np.exp(-(rho - 0.92) / 0.03))
    error_rate = 0.0008 + 0.22 * err_lat + 0.28 * err_cpu + 0.20 * err_rho
    error_rate = np.clip(error_rate + rng.normal(0, 0.0006, size=len(error_rate)), 0, 0.85)
    return cpu, memory, network, latency, error_rate, rho


def _capacity_from_hidden(query_weight, bg_cpu, bg_ram):
    """Largest user count that still meets all three SLAs, given hidden state."""
    n_eff = N_WORKERS * np.clip(1.0 - bg_cpu / 100.0, 0.15, 1.0)
    service_s = (BASE_SERVICE_MS * query_weight) / 1000.0

    # CPU constraint: bg + CPU_PER_RPS * rps * qw <= SLA_CPU
    rps_cpu = np.maximum(0.0, (SLA_CPU - bg_cpu) / (CPU_PER_RPS * query_weight))

    # Latency constraint: invert the M/M/c-style formula at SLA_LATENCY
    # latency ≈ service_ms/(1-rho) + 8  (ignore the post-knee term, stay below it)
    service_ms = BASE_SERVICE_MS * query_weight
    denom = SLA_LATENCY_MS - 8.0
    # service_ms / (1-rho) + 8 <= SLA  →  1-rho >= service_ms/(SLA-8)
    min_idle = np.clip(service_ms / np.maximum(denom, 1.0), 0.02, 0.95)
    max_rho = 1.0 - min_idle
    rps_lat = max_rho * n_eff / service_s

    rps_cap = np.minimum(rps_cpu, rps_lat)
    users_cap = np.floor(rps_cap * THINK_TIME_S)
    return np.clip(users_cap, 200, 30000).astype(int)


def build() -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    rng = np.random.default_rng(SEED)
    nasa = pd.read_csv(SEL / "nasa_minute.csv", parse_dates=["timestamp"])
    uni = pd.read_csv(SEL / "university_minute.csv", parse_dates=["timestamp"])

    # Continuous minute index over NASA's observed window
    full_idx = pd.date_range(nasa["timestamp"].min(), nasa["timestamp"].max(), freq="min")
    nasa = nasa.set_index("timestamp").reindex(full_idx)
    nasa.index.name = "nasa_timestamp"
    nasa["requests"] = nasa["requests"].fillna(0)
    nasa["unique_hosts"] = nasa["unique_hosts"].fillna(0)
    nasa["error_rate"] = nasa["error_rate"].fillna(0)
    nasa["bytes_total"] = nasa["bytes_total"].fillna(0)

    # University burstiness: coefficient of variation of occupied minutes
    uni_cv = float(uni["requests"].std() / max(uni["requests"].mean(), 1e-6))

    hosts = nasa["unique_hosts"].to_numpy(dtype=float)
    reqs = nasa["requests"].to_numpy(dtype=float)

    # Scale NASA shape to ERP magnitudes (rank-preserving)
    host_p50 = np.percentile(hosts[hosts > 0], 50)
    host_p99 = np.percentile(hosts[hosts > 0], 99)
    # Proportional scale keeps NASA's rank order. p50 hosts → 2600 ERP users.
    # The p99 host spike is then ~8–9k users; the absolute NASA max is clipped.
    users_raw = TARGET_P50_USERS * (hosts / max(host_p50, 1.0))
    users_raw = np.clip(users_raw, 60, TARGET_PEAK_USERS)

    req_p50 = np.percentile(reqs[reqs > 0], 50)
    rps_from_req = (reqs / max(req_p50, 1.0)) * (TARGET_P50_USERS / THINK_TIME_S) * 0.45
    rps_from_users = users_raw / THINK_TIME_S
    rps = 0.70 * rps_from_users + 0.30 * rps_from_req
    rps = np.clip(rps, 0.2, 2500)

    n = len(nasa)
    hour = nasa.index.hour.to_numpy()
    dow = nasa.index.dayofweek.to_numpy()
    is_weekend = (dow >= 5).astype(int)

    # Result windows: NASA's heaviest calendar days (real peaks), plus one midweek window
    daily = nasa["requests"].groupby(nasa.index.date).sum()
    top_days = set(daily.sort_values(ascending=False).head(3).index)
    is_result = np.array([d in top_days for d in nasa.index.date], dtype=int)
    # result-day query mix is heavier (grade sheets, PDFs, many DB joins)
    query_weight = 1.0 + 0.55 * is_result + 0.08 * (hour >= 10).astype(float) * (hour <= 16).astype(float)
    query_weight = query_weight + rng.normal(0, 0.03, size=n)
    query_weight = np.clip(query_weight, 0.85, 2.2)

    # Hidden headroom: batch jobs / other tenants. Not given to Team 2.
    # Slow daily cycle + noise so the same (users, cpu) can map to different capacity.
    tod = (np.sin((hour - 3) / 24.0 * 2 * np.pi) + 1) / 2
    bg_cpu = 7.0 + 10.0 * tod + rng.normal(0, 1.4, size=n)
    bg_cpu = np.clip(bg_cpu + 4.5 * is_result, 4.0, 28.0)
    bg_ram = 18.0 + 6.0 * tod + rng.normal(0, 1.1, size=n)
    bg_ram = np.clip(bg_ram, 14.0, 40.0)

    # Mild extra burstiness borrowed from the university CV (not invented requests)
    burst = 1.0 + 0.04 * np.clip(uni_cv / 2.0, 0, 3) * rng.normal(0, 1, size=n)
    users = np.clip(users_raw * np.clip(burst, 0.85, 1.2), 50, TARGET_PEAK_USERS)
    rps = rps * np.clip(burst, 0.85, 1.2)

    cpu, memory, network, latency, error_rate, rho = _telemetry(
        users, rps, query_weight, bg_cpu, bg_ram, rng
    )
    safe_capacity = _capacity_from_hidden(query_weight, bg_cpu, bg_ram)
    util = users / np.maximum(safe_capacity, 1)
    sla_breach = (latency > SLA_LATENCY_MS) | (error_rate > SLA_ERROR_RATE) | (cpu > SLA_CPU)
    risk_level = _risk_from_util(util, sla_breach)

    # Remap NASA July 1995 onto a 2025 academic-calendar window (same length, same shape)
    start = pd.Timestamp("2025-06-16 00:00:00")
    timestamps = start + pd.to_timedelta(np.arange(n), unit="min")

    clean_proto = pd.DataFrame(
        {
            "timestamp": timestamps,
            "hour": timestamps.hour,
            "day_of_week": timestamps.dayofweek,
            "is_weekend": (timestamps.dayofweek >= 5).astype(int),
            "is_result_window": is_result,
            "concurrent_users": np.rint(users).astype(int),
            "requests_per_sec": np.round(rps, 3),
            "cpu_usage": np.round(cpu, 2),
            "memory_usage": np.round(memory, 2),
            "network_usage": np.round(network, 2),
            "latency_ms": np.round(latency, 1),
            "error_rate": np.round(error_rate, 5),
            "safe_capacity": safe_capacity,
            "risk_level": risk_level,
        }
    )

    # --- inject realistic raw defects, then clean them (documented) ---
    raw = clean_proto.copy()
    dup_src = rng.choice(n, size=18, replace=False)
    raw = pd.concat([raw, raw.iloc[dup_src].copy()], ignore_index=True)
    miss_idx = rng.choice(len(raw), size=int(0.0025 * n), replace=False)
    raw.loc[miss_idx, ["cpu_usage", "memory_usage"]] = np.nan
    spike_idx = rng.choice(len(raw), size=6, replace=False)
    raw.loc[spike_idx, "cpu_usage"] = 999.0  # broken sensor
    raw.loc[rng.choice(len(raw), size=4, replace=False), "latency_ms"] = -15.0
    raw["scratch_trace_id"] = rng.integers(0, 1_000_000, size=len(raw))  # irrelevant

    stats = {
        "nasa_minutes_occupied": int((reqs > 0).sum()),
        "nasa_minutes_full_index": n,
        "university_minutes": int(len(uni)),
        "university_cv": uni_cv,
        "host_p50": float(host_p50),
        "host_p99": float(host_p99),
        "raw_rows": int(len(raw)),
        "raw_dups": int(raw.duplicated().sum()),
        "raw_missing_cpu": int(raw["cpu_usage"].isna().sum()),
        "raw_sensor_spikes": int((raw["cpu_usage"] > 100).sum()),
        "raw_negative_latency": int((raw["latency_ms"] < 0).sum()),
        "result_minutes": int(is_result.sum()),
        "risk_counts": clean_proto["risk_level"].value_counts().to_dict(),
        "safe_capacity_p50": int(np.median(safe_capacity)),
        "users_p50": int(np.median(users)),
        "users_max": int(users.max()),
        "latency_p50": float(np.median(latency)),
        "latency_p95": float(np.percentile(latency, 95)),
    }
    return raw, clean_proto, stats


def clean(raw: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    log: list[str] = []
    df = raw.copy()
    if "scratch_trace_id" in df.columns:
        df = df.drop(columns=["scratch_trace_id"])
        log.append("Dropped irrelevant column `scratch_trace_id` (internal trace id, not a feature).")

    before = len(df)
    df = df.drop_duplicates()
    log.append(f"Removed {before - len(df)} duplicate rows ({before} → {len(df)}).")

    bad_sensor = (df["cpu_usage"] > 100) | (df["latency_ms"] < 0)
    log.append(
        f"Removed {int(bad_sensor.sum())} impossible sensor rows "
        f"(cpu_usage>100 or latency_ms<0)."
    )
    df = df.loc[~bad_sensor]

    miss = df[["cpu_usage", "memory_usage", "network_usage", "latency_ms"]].isna().any(axis=1)
    log.append(f"Removed {int(miss.sum())} rows with missing CPU/RAM (monitoring dropouts, {miss.mean():.2%} of remaining).")
    df = df.loc[~miss]

    for col in ["cpu_usage", "memory_usage", "network_usage"]:
        df[col] = df[col].clip(0, 100)
    df["error_rate"] = df["error_rate"].clip(0, 1)
    df["concurrent_users"] = df["concurrent_users"].clip(lower=0)
    df["requests_per_sec"] = df["requests_per_sec"].clip(lower=0)
    log.append("Clipped cpu/memory/network to [0, 100], error_rate to [0, 1], users/rps to ≥ 0.")

    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df["hour"] = df["timestamp"].dt.hour.astype(int)
    df["day_of_week"] = df["timestamp"].dt.dayofweek.astype(int)
    df["is_weekend"] = df["is_weekend"].astype(int)
    df["is_result_window"] = df["is_result_window"].astype(int)
    df["concurrent_users"] = df["concurrent_users"].astype(int)
    df["safe_capacity"] = df["safe_capacity"].astype(int)
    df["risk_level"] = df["risk_level"].astype(str)
    log.append("Fixed dtypes: timestamps datetime, flags/ints, risk_level string.")

    df = df.sort_values("timestamp").reset_index(drop=True)
    log.append(f"Sorted by timestamp. Final shape: {df.shape[0]} rows × {df.shape[1]} columns.")
    return df, log


def main() -> None:
    PROC.mkdir(parents=True, exist_ok=True)
    raw, proto, stats = build()
    clean_df, log = clean(raw)

    raw_path = PROC / "dataset_raw.csv"
    clean_path = PROC / "dataset_clean.csv"
    raw.to_csv(raw_path, index=False)
    clean_df.to_csv(clean_path, index=False)

    lines = ["# Cleaning log", "", "Applied only after selection and target definition.", ""]
    for item in log:
        lines.append(f"- {item}")
    lines += [
        "",
        "## Build stats",
        f"- NASA occupied minutes: {stats['nasa_minutes_occupied']}",
        f"- Full reindexed minutes: {stats['nasa_minutes_full_index']}",
        f"- University occupied minutes: {stats['university_minutes']}",
        f"- University request CV (burstiness used as a small mixer): {stats['university_cv']:.3f}",
        f"- NASA unique_hosts p50/p99: {stats['host_p50']:.1f} / {stats['host_p99']:.1f}",
        f"- Result-window minutes: {stats['result_minutes']}",
        f"- Risk counts (pre-clean prototype): {stats['risk_counts']}",
        f"- Users p50/max: {stats['users_p50']} / {stats['users_max']}",
        f"- safe_capacity p50: {stats['safe_capacity_p50']}",
        f"- Latency p50/p95: {stats['latency_p50']:.1f} / {stats['latency_p95']:.1f} ms",
        "",
        "Team 2 must split `dataset_clean.csv` themselves. No train/val/test files are produced here.",
    ]
    (PROC / "cleaning_log.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    print(f"wrote {raw_path}")
    print(f"wrote {clean_path}")
    print(clean_df.head(3).to_string(index=False))
    print(clean_df["risk_level"].value_counts().to_string())


if __name__ == "__main__":
    main()
