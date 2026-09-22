#!/usr/bin/env python3
"""Export telemetry simulation results to JSON and CSV formats."""

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from week2.team1_simulation.telemetry_synthesizer import synthesize_telemetry

if __name__ == "__main__":
    scenarios = [
        "Result Declaration Rush",
        "Regular Academic Day",
        "Exam Fee Registration",
        "Course Registration Rush",
        "Off-Peak Night",
    ]
    records = []
    for sc in scenarios:
        for u in [1000, 3000, 5000, 8000, 10000, 12000, 15000]:
            records.append(synthesize_telemetry(sc, u))

    df = pd.DataFrame(records)
    out_csv = ROOT / "traffic_bot_model" / "telemetry_snapshot.csv"
    df.to_csv(out_csv, index=False)
    print(f"✅ Exported {len(records)} telemetry records to {out_csv}")
