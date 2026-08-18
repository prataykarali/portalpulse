"""Export the frozen Week 1 data package. Does not retrain or reclean."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "Module1_Data" / "dataset_clean.csv"
OUT = ROOT / "Module1_Data"

# Preferred Team 1 split (time-based, from feature_notes.md):
# last 5 calendar days = test, the 3 days before that = validation.
VAL_START = pd.Timestamp("2025-07-06")
TEST_START = pd.Timestamp("2025-07-09")

DICTIONARY = [
    {
        "column": "timestamp",
        "meaning": "Start of the 1-minute window (naive local clock on the 2025 academic observation window)",
        "type": "datetime",
        "role": "index / time feature",
        "allowed_values": "2025-06-16 00:00 → 2025-07-13 13:32",
        "notes": "Leave out of the model matrix. Use only to split and to derive hour / day flags.",
    },
    {
        "column": "hour",
        "meaning": "Hour of day extracted from timestamp",
        "type": "integer",
        "role": "feature",
        "allowed_values": "0–23",
        "notes": "Captures the real NASA diurnal shape.",
    },
    {
        "column": "day_of_week",
        "meaning": "Monday=0 … Sunday=6",
        "type": "integer",
        "role": "feature",
        "allowed_values": "0–6",
        "notes": "",
    },
    {
        "column": "is_weekend",
        "meaning": "1 if Saturday or Sunday",
        "type": "integer (flag)",
        "role": "feature",
        "allowed_values": "0 or 1",
        "notes": "Derived from day_of_week.",
    },
    {
        "column": "is_result_window",
        "meaning": "1 if this minute falls on a known heavy result / announcement day",
        "type": "integer (flag)",
        "role": "feature",
        "allowed_values": "0 or 1",
        "notes": "Legitimate calendar feature — result dates are known in advance. Not leakage.",
    },
    {
        "column": "concurrent_users",
        "meaning": "Active users in the minute",
        "type": "integer",
        "role": "feature",
        "allowed_values": "56–12,500",
        "notes": "Scaled from NASA unique hosts; rank order of the real load is preserved.",
    },
    {
        "column": "requests_per_sec",
        "meaning": "HTTP arrival rate",
        "type": "float",
        "role": "feature",
        "allowed_values": "≈ 5.6–1,769",
        "notes": "Mixture of host-implied and request-implied NASA intensity.",
    },
    {
        "column": "cpu_usage",
        "meaning": "CPU utilization",
        "type": "float (%)",
        "role": "feature",
        "allowed_values": "0–100",
        "notes": "Strongest saturation signal.",
    },
    {
        "column": "memory_usage",
        "meaning": "RAM utilization",
        "type": "float (%)",
        "role": "feature",
        "allowed_values": "0–100",
        "notes": "Softer constraint than CPU.",
    },
    {
        "column": "network_usage",
        "meaning": "Network utilization",
        "type": "float (%)",
        "role": "feature",
        "allowed_values": "0–100",
        "notes": "Rises with RPS and heavier result-day payloads.",
    },
    {
        "column": "latency_ms",
        "meaning": "Mean response time in the minute",
        "type": "float (ms)",
        "role": "feature",
        "allowed_values": "≥ 15",
        "notes": "SLA line used to label the target is 800 ms.",
    },
    {
        "column": "error_rate",
        "meaning": "Fraction of failed requests in the minute",
        "type": "float",
        "role": "feature",
        "allowed_values": "0–1",
        "notes": "SLA line used to label the target is 0.01 (1%).",
    },
    {
        "column": "safe_capacity",
        "meaning": "Maximum concurrent users the system can still serve without breaching SLA, given current hidden headroom",
        "type": "integer",
        "role": "primary target",
        "allowed_values": "3,626–9,248",
        "notes": "Regression target. Not a live IEM measurement. Do not use as a feature.",
    },
    {
        "column": "risk_level",
        "meaning": "Operating-risk class derived from utilization and live SLA breach",
        "type": "string",
        "role": "derived target",
        "allowed_values": "SAFE / AT_RISK / OVERLOADED",
        "notes": "SAFE <70% util, AT_RISK 70–90%, OVERLOADED ≥90% or already breaching SLA.",
    },
]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def split_frame(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    train = df[df["timestamp"] < VAL_START].copy()
    val = df[(df["timestamp"] >= VAL_START) & (df["timestamp"] < TEST_START)].copy()
    test = df[df["timestamp"] >= TEST_START].copy()
    return train, val, test


def describe(name: str, frame: pd.DataFrame) -> dict:
    return {
        "rows": int(len(frame)),
        "start": str(frame["timestamp"].min()),
        "end": str(frame["timestamp"].max()),
        "risk_counts": frame["risk_level"].value_counts().to_dict(),
    }


def main() -> None:
    if not SRC.exists():
        raise SystemExit(f"missing {SRC}")

    master_path = OUT / "master_clean.csv"
    if master_path.resolve() != SRC.resolve():
        shutil.copy2(SRC, master_path)

    df = pd.read_csv(master_path, parse_dates=["timestamp"])
    train, val, test = split_frame(df)

    train_path = OUT / "train.csv"
    val_path = OUT / "validation.csv"
    test_path = OUT / "test.csv"
    train.to_csv(train_path, index=False)
    val.to_csv(val_path, index=False)
    test.to_csv(test_path, index=False)

    dict_path = OUT / "data_dictionary.csv"
    pd.DataFrame(DICTIONARY).to_csv(dict_path, index=False)

    manifest = {
        "frozen": True,
        "week": "Module 1 / Week 1",
        "grain": "one row = one minute",
        "master": "master_clean.csv",
        "source_alias": "dataset_clean.csv",
        "columns": list(df.columns),
        "master_rows": int(len(df)),
        "master_cols": int(df.shape[1]),
        "missing_values": int(df.isna().sum().sum()),
        "duplicates": int(df.duplicated().sum()),
        "date_range": {
            "start": str(df["timestamp"].min()),
            "end": str(df["timestamp"].max()),
            "calendar_days": int(df["timestamp"].dt.date.nunique()),
        },
        "cleaning": {
            "raw_rows": 39711,
            "removed_total": 127,
            "duplicates_removed": 18,
            "impossible_sensor_rows_removed": 10,
            "monitoring_dropouts_removed": 99,
            "clean_rows": 39584,
        },
        "split": {
            "method": "time",
            "rule": "last 5 calendar days = test; 3 days before that = validation; remainder = train",
            "validation_start": str(VAL_START),
            "test_start": str(TEST_START),
            "train": describe("train", train),
            "validation": describe("validation", val),
            "test": describe("test", test),
        },
        "sha256": {
            "master_clean.csv": sha256(master_path),
            "train.csv": sha256(train_path),
            "validation.csv": sha256(val_path),
            "test.csv": sha256(test_path),
            "data_dictionary.csv": sha256(dict_path),
        },
        "note": (
            "Team 1 originally handed over one master file. This freeze publishes the "
            "recommended time split so Week 2 does not retrain on a random shuffle. "
            "The original XGBoost training-row split was not checked in."
        ),
    }
    (OUT / "split_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({k: manifest[k] for k in ("master_rows", "split")}, indent=2))


if __name__ == "__main__":
    main()
