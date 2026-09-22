"""Unit tests for PortalPulse SQLite persistence and Hybrid Redis caching."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dashboard.db import (
    add_student,
    get_student_results,
    init_db,
)


class TestDatabase(unittest.TestCase):
    def setUp(self):
        init_db()

    def test_add_and_query_student(self):
        enroll = "2024TEST999"
        ok, _msg = add_student(
            enrollment_no=enroll,
            name="Test Student",
            email="test.student@iem.edu.in",
            department="Computer Science & Engineering",
            year=2,
            semester=4,
            cgpa=9.2,
        )
        self.assertTrue(ok)
        res = get_student_results(enroll, bypass_cache=True)
        self.assertTrue(res["found"])
        self.assertEqual(res["student"]["name"], "Test Student")
        self.assertEqual(len(res["results"]), 20)

    def test_cache_hit_behavior(self):
        enroll = "2024TEST999"
        # First query warms cache
        _ = get_student_results(enroll, bypass_cache=False)
        # Second query should hit cache
        res2 = get_student_results(enroll, bypass_cache=False)
        self.assertTrue(res2["cache_hit"])


if __name__ == "__main__":
    unittest.main()
