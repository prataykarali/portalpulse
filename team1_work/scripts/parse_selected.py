"""Parse the two selected raw traces into minute-level tables.

Primary:   NASA HTTP Jul95 access log
Secondary: University Apache labeled access log (BKD / lecturer-workload ERP)
"""

from __future__ import annotations

import gzip
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
CAND = ROOT / "team1_work" / "candidates"
SEL = ROOT / "team1_work" / "selected"

NASA_RE = re.compile(
    r'^(\S+) \S+ \S+ \[(\d{2}/\w{3}/\d{4}:\d{2}:\d{2}:\d{2}) [^\]]+\] '
    r'"[^"]*" (\d{3}) (\d+|-)'
)
UNI_RE = re.compile(
    r"(GET|POST|PUT|DELETE|HEAD|PATCH)\s+(\S+)\s+HTTP/\d\.\d\s+(\d{3})\s+(\d+)"
)


def parse_nasa() -> pd.DataFrame:
    src = CAND / "NASA_access_log_Jul95.gz"
    buckets: dict[datetime, dict] = defaultdict(
        lambda: {
            "requests": 0,
            "hosts": set(),
            "bytes": 0,
            "status_2xx": 0,
            "status_3xx": 0,
            "status_4xx": 0,
            "status_5xx": 0,
        }
    )
    parsed = 0
    skipped = 0
    with gzip.open(src, "rt", errors="replace") as fh:
        for line in fh:
            m = NASA_RE.search(line)
            if not m:
                skipped += 1
                continue
            host, ts_raw, status_s, bytes_s = m.groups()
            try:
                ts = datetime.strptime(ts_raw, "%d/%b/%Y:%H:%M:%S").replace(second=0)
            except ValueError:
                skipped += 1
                continue
            status = int(status_s)
            nbytes = int(bytes_s) if bytes_s.isdigit() else 0
            b = buckets[ts]
            b["requests"] += 1
            b["hosts"].add(host)
            b["bytes"] += nbytes
            if 200 <= status < 300:
                b["status_2xx"] += 1
            elif 300 <= status < 400:
                b["status_3xx"] += 1
            elif 400 <= status < 500:
                b["status_4xx"] += 1
            else:
                b["status_5xx"] += 1
            parsed += 1

    rows = []
    for ts, b in buckets.items():
        rows.append(
            {
                "timestamp": ts,
                "requests": b["requests"],
                "unique_hosts": len(b["hosts"]),
                "bytes_total": b["bytes"],
                "status_2xx": b["status_2xx"],
                "status_3xx": b["status_3xx"],
                "status_4xx": b["status_4xx"],
                "status_5xx": b["status_5xx"],
                "error_rate": (b["status_4xx"] + b["status_5xx"]) / b["requests"],
            }
        )
    df = pd.DataFrame(rows).sort_values("timestamp").reset_index(drop=True)
    print(f"NASA parsed={parsed:,} skipped={skipped:,} minutes={len(df):,}")
    print(df.describe(include="all").T)
    return df


def parse_university() -> pd.DataFrame:
    src = CAND / "A_apache_access_labeled.csv"
    raw = pd.read_csv(src)
    extracted = raw["log"].str.extract(UNI_RE)
    extracted.columns = ["method", "path", "status", "bytes"]
    df = raw.join(extracted)
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df["status"] = pd.to_numeric(df["status"], errors="coerce")
    df["bytes"] = pd.to_numeric(df["bytes"], errors="coerce")
    df["is_error"] = df["status"] >= 400
    g = (
        df.dropna(subset=["timestamp"])
        .groupby("timestamp")
        .agg(
            requests=("log", "size"),
            parsed_requests=("status", "count"),
            bytes_total=("bytes", "sum"),
            error_requests=("is_error", "sum"),
            label_bahaya=("label", lambda s: int((s == "BAHAYA").sum())),
            label_aman=("label", lambda s: int((s == "AMAN").sum())),
            label_dicurigai=("label", lambda s: int((s == "DICURIGAI").sum())),
        )
        .reset_index()
    )
    g["error_rate"] = g["error_requests"] / g["requests"]
    print(f"University minutes={len(g):,} raw_rows={len(raw):,}")
    print(g.describe(include="all").T)
    return g


def main() -> None:
    SEL.mkdir(parents=True, exist_ok=True)
    nasa = parse_nasa()
    uni = parse_university()
    nasa_path = SEL / "nasa_minute.csv"
    uni_path = SEL / "university_minute.csv"
    nasa.to_csv(nasa_path, index=False)
    uni.to_csv(uni_path, index=False)
    print(f"wrote {nasa_path} ({len(nasa)} rows)")
    print(f"wrote {uni_path} ({len(uni)} rows)")


if __name__ == "__main__":
    main()
