#!/usr/bin/env python3
"""Standalone script to seed PortalPulse database with realistic academic records."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dashboard.db import get_db_stats, init_db, seed_sample_students

if __name__ == "__main__":
    print("🌱 Initializing database...")
    init_db()
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 150
    print(f"📊 Seeding {count} student records...")
    inserted = seed_sample_students(count=count)
    stats = get_db_stats()
    print(f"✅ Successfully seeded {inserted} students!")
    print(f"📈 Total Students: {stats['student_count']:,} | Total Result Rows: {stats['result_count']:,}")
    print(f"💾 DB Size on Disk: {stats['db_size_kb']} KB")
