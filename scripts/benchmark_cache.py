#!/usr/bin/env python3
"""Empirical CLI benchmark comparing Cold SQLite reads vs Redis Cache hits."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dashboard.db import run_db_stress_benchmark

if __name__ == "__main__":
    queries = int(sys.argv[1]) if len(sys.argv) > 1 else 80
    print(f"⚡ Running {queries}-query latency benchmark (Cold DB vs Redis Cache)...")
    res = run_db_stress_benchmark(num_queries=queries)
    if "error" in res:
        print(f"❌ Error: {res['error']}")
    else:
        print("-" * 50)
        print(f"📊 Total Queries: {res['num_queries']}")
        print(f"🐢 Cold SQLite Avg Latency:  {res['cold_avg_ms']} ms (P95: {res['cold_p95_ms']} ms)")
        print(f"⚡ Redis Cache Avg Latency:   {res['cached_avg_ms']} ms (P95: {res['cached_p95_ms']} ms)")
        print(f"🚀 Speedup Factor:            {res['speedup_factor']}x faster with caching!")
        print("-" * 50)
