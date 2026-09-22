"""Unit tests for Database Repository Adapter and Hybrid Redis Caching Layer."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dashboard.db import (
    DB_ADAPTER,
    add_student,
    get_all_faculty,
    get_db_stats,
    get_student_results,
    get_students_by_department,
    init_db,
    run_db_stress_benchmark,
    update_student_grade,
)


class TestDatabaseAdapter(unittest.TestCase):
    def setUp(self):
        init_db()

    def test_adapter_metrics(self):
        metrics = DB_ADAPTER.get_metrics()
        self.assertIn("SQLite 3", metrics["engine"])
        self.assertGreaterEqual(metrics["max_pool_size"], 100)
        self.assertIn("migration_ready", metrics)

    def test_student_crud_and_idempotency(self):
        enroll = "2024TEST888"
        ok, _msg = add_student(
            enrollment_no=enroll,
            name="Arch Test Student",
            email="arch.test@iem.edu.in",
            department="Computer Science & Engineering",
            year=3,
            semester=5,
            cgpa=9.4,
        )
        self.assertTrue(ok)
        res = get_student_results(enroll, bypass_cache=True)
        self.assertTrue(res["found"])
        self.assertEqual(res["student"]["name"], "Arch Test Student")
        self.assertEqual(len(res["results"]), 25)

    def test_grade_update_and_cache_invalidation(self):
        enroll = "2024TEST777"
        add_student(
            enrollment_no=enroll,
            name="Cache Test Student",
            email="cache.test@iem.edu.in",
            department="Computer Science & Engineering",
            year=2,
            semester=4,
            cgpa=9.1,
        )
        # First read seeds cache (cold query)
        res1 = get_student_results(enroll, bypass_cache=False)
        self.assertFalse(res1["cache_hit"])

        # Second read hits cache
        res2 = get_student_results(enroll, bypass_cache=False)
        self.assertTrue(res2["cache_hit"])

        # Update grade invalidates cache
        sub_code = res1["results"][0]["subject_code"]
        sem = res1["results"][0]["semester"]
        ok, _msg = update_student_grade(enroll, sem, sub_code, "O", 10.0)
        self.assertTrue(ok)

        # Third read should be a cache miss due to invalidation
        res3 = get_student_results(enroll, bypass_cache=False)
        self.assertFalse(res3["cache_hit"])

    def test_faculty_directory(self):
        faculty = get_all_faculty()
        self.assertGreaterEqual(len(faculty), 4)
        self.assertIn("faculty_id", faculty[0])

    def test_department_filter(self):
        students_cse = get_students_by_department("Computer Science & Engineering")
        self.assertIsInstance(students_cse, list)

    def test_db_stats_payload(self):
        stats = get_db_stats()
        self.assertGreater(stats["student_count"], 0)
        self.assertGreater(stats["faculty_count"], 0)
        self.assertIn("cache", stats)
        self.assertIn("adapter", stats)

    def test_stress_benchmark(self):
        bench = run_db_stress_benchmark(num_queries=10)
        self.assertIn("speedup_factor", bench)
        self.assertGreater(bench["num_queries"], 0)


if __name__ == "__main__":
    unittest.main()
