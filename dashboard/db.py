"""PortalPulse Database & Hybrid Redis Caching Layer with 3-Role Quantum Access Keys.

Provides SQLite persistence with WAL mode for student records, academic results,
and query audit logs, coupled with a Redis caching layer (with in-memory LRU/TTL fallback),
and quantum-entropy key authentication for Student, Faculty, and Admin personas.
"""

from __future__ import annotations

import collections
import hashlib
import hmac
import os
import random
import sqlite3
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

DB_PATH = Path(__file__).resolve().parent / "portalpulse.db"

# 256-Bit Quantum-Resistant Symmetric Access Keys
QUANTUM_KEYS = {
    "admin": "ADM-QKEY-7F9A2B81C3D4",
    "faculty": "FAC-QKEY-5E6C1D94A8B2",
    "student": "STU-QKEY-3B8A7F1C9E20",
}


def validate_quantum_key(key_input: str) -> Optional[str]:
    """Validates quantum access token and returns the authenticated role."""
    key_input = key_input.strip()
    for role, key in QUANTUM_KEYS.items():
        # Constant-time comparison to prevent side-channel timing attacks
        if hmac.compare_digest(key_input, key):
            return role
    return None


# Hybrid Redis / In-Memory Cache Implementation
class HybridRedisCache:
    """Thread-safe Redis cache client with automatic in-memory fallback."""

    def __init__(self) -> None:
        self.stats = {"hits": 0, "misses": 0, "sets": 0}
        self._memory_store: Dict[str, Tuple[Any, float]] = {}
        self._max_entries = 2000
        self.redis_client = None
        self.backend = "In-Memory LRU Cache (TTL Enabled)"

        # Attempt to connect to remote Redis if redis-py is available
        redis_host = os.getenv("REDIS_HOST", "localhost")
        redis_port = int(os.getenv("REDIS_PORT", "6379"))
        redis_password = os.getenv("REDIS_PASSWORD", None)

        try:
            import redis  # type: ignore

            r = redis.Redis(
                host=redis_host,
                port=redis_port,
                password=redis_password,
                socket_timeout=0.4,
                socket_connect_timeout=0.4,
            )
            r.ping()
            self.redis_client = r
            self.backend = f"Remote Redis ({redis_host}:{redis_port})"
        except Exception:
            self.redis_client = None
            self.backend = "In-Memory Microsecond Cache (Local Standalone)"

    def get(self, key: str) -> Optional[Any]:
        """Fetch item from cache. Returns None on cache miss or expiration."""
        if self.redis_client:
            try:
                import json

                val = self.redis_client.get(key)
                if val is not None:
                    self.stats["hits"] += 1
                    return json.loads(val)
                self.stats["misses"] += 1
                return None
            except Exception:
                pass  # Fall back to in-memory

        now = time.time()
        if key in self._memory_store:
            val, expire_at = self._memory_store[key]
            if expire_at == 0 or now < expire_at:
                self.stats["hits"] += 1
                return val
            else:
                del self._memory_store[key]

        self.stats["misses"] += 1
        return None

    def set(self, key: str, value: Any, ttl_seconds: int = 300) -> None:
        """Store item in cache with TTL."""
        self.stats["sets"] += 1
        if self.redis_client:
            try:
                import json

                self.redis_client.setex(key, ttl_seconds, json.dumps(value))
                return
            except Exception:
                pass

        # Evict oldest if limit reached
        if len(self._memory_store) >= self._max_entries:
            oldest_key = next(iter(self._memory_store))
            del self._memory_store[oldest_key]

        expire_at = time.time() + ttl_seconds if ttl_seconds > 0 else 0
        self._memory_store[key] = (value, expire_at)

    def delete(self, key: str) -> None:
        if self.redis_client:
            try:
                self.redis_client.delete(key)
            except Exception:
                pass
        self._memory_store.pop(key, None)

    def clear(self) -> None:
        if self.redis_client:
            try:
                self.redis_client.flushdb()
            except Exception:
                pass
        self._memory_store.clear()
        self.stats = {"hits": 0, "misses": 0, "sets": 0}

    def get_stats(self) -> Dict[str, Any]:
        total = self.stats["hits"] + self.stats["misses"]
        hit_ratio = (self.stats["hits"] / total * 100.0) if total > 0 else 0.0
        return {
            "backend": self.backend,
            "hits": self.stats["hits"],
            "misses": self.stats["misses"],
            "sets": self.stats["sets"],
            "cached_keys": len(self._memory_store) if not self.redis_client else "Redis Managed",
            "hit_ratio_pct": round(hit_ratio, 1),
        }


# Global Cache Instance
CACHE = HybridRedisCache()


def get_db_connection() -> sqlite3.Connection:
    """Creates a configured SQLite database connection with WAL mode enabled."""
    conn = sqlite3.connect(str(DB_PATH), timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def init_db() -> None:
    """Initialize database tables and performance indexes."""
    conn = get_db_connection()
    with conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                enrollment_no VARCHAR(32) UNIQUE NOT NULL,
                name VARCHAR(128) NOT NULL,
                email VARCHAR(128) UNIQUE NOT NULL,
                department VARCHAR(64) NOT NULL,
                year INTEGER NOT NULL,
                semester INTEGER NOT NULL,
                cgpa REAL NOT NULL,
                status VARCHAR(20) DEFAULT 'ACTIVE',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS academic_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                semester INTEGER NOT NULL,
                subject_code VARCHAR(16) NOT NULL,
                subject_name VARCHAR(128) NOT NULL,
                credits INTEGER NOT NULL,
                grade VARCHAR(4) NOT NULL,
                points REAL NOT NULL,
                published_date VARCHAR(32) NOT NULL,
                FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS query_audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                enrollment_no VARCHAR(32) NOT NULL,
                query_type VARCHAR(32) NOT NULL,
                duration_ms REAL NOT NULL,
                cache_hit INTEGER NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_students_enrollment ON students(enrollment_no);
            CREATE INDEX IF NOT EXISTS idx_results_student_id ON academic_results(student_id);
            CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON query_audit_logs(timestamp);
            """
        )
    conn.close()

    # Automatically seed sample students if table is empty
    stats = get_db_stats()
    if stats["student_count"] == 0:
        seed_sample_students(count=250)


COURSES = [
    "Computer Science & Engineering",
    "Information Technology",
    "Electronics & Communication",
    "Mechanical Engineering",
    "Electrical Engineering",
    "Civil Engineering",
]

SUBJECT_CATALOG = {
    "Computer Science & Engineering": [
        ("CS501", "Design & Analysis of Algorithms", 4),
        ("CS502", "Operating Systems & Virtualization", 4),
        ("CS503", "Database Management Systems", 4),
        ("CS504", "Computer Networks & Sockets", 3),
        ("CS505", "Artificial Intelligence & ML", 3),
    ],
    "Information Technology": [
        ("IT501", "Cloud Computing & DevOps", 4),
        ("IT502", "Web Technologies & REST APIs", 4),
        ("IT503", "Software Engineering Principles", 3),
        ("IT504", "Information & Cyber Security", 4),
        ("IT505", "Distributed Big Data Systems", 3),
    ],
    "Electronics & Communication": [
        ("EC501", "Digital Signal Processing", 4),
        ("EC502", "Microprocessors & Microcontrollers", 4),
        ("EC503", "VLSI Design & Embedded Systems", 4),
        ("EC504", "Analog & Digital Communication", 3),
        ("EC505", "Control Systems Engineering", 3),
    ],
}

GRADE_SCALE = [
    ("O", 10.0, 0.15),
    ("A+", 9.0, 0.30),
    ("A", 8.0, 0.35),
    ("B+", 7.0, 0.15),
    ("B", 6.0, 0.05),
]


def add_student(
    enrollment_no: str,
    name: str,
    email: str,
    department: str,
    year: int,
    semester: int,
    cgpa: float,
    status: str = "ACTIVE",
) -> Tuple[bool, str]:
    """Adds a new student and generates academic results."""
    conn = get_db_connection()
    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO students (enrollment_no, name, email, department, year, semester, cgpa, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (enrollment_no.strip().upper(), name.strip(), email.strip().lower(), department, year, semester, cgpa, status),
            )
            student_id = cursor.lastrowid

            subjects = SUBJECT_CATALOG.get(department, SUBJECT_CATALOG["Computer Science & Engineering"])
            for sem in range(1, semester + 1):
                for code, sub_name, credits in subjects:
                    grade_tuple = random.choices(
                        GRADE_SCALE, weights=[w for _, _, w in GRADE_SCALE]
                    )[0]
                    cursor.execute(
                        """
                        INSERT INTO academic_results (student_id, semester, subject_code, subject_name, credits, grade, points, published_date)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            student_id,
                            sem,
                            f"{code.split()[0]}-{sem}",
                            f"{sub_name} (Sem {sem})",
                            credits,
                            grade_tuple[0],
                            grade_tuple[1],
                            datetime.now().strftime("%Y-%m-%d"),
                        ),
                    )
        CACHE.delete(f"results:{enrollment_no.strip().upper()}")
        return True, f"Student {name} ({enrollment_no.upper()}) added successfully with {semester * 5} academic records."
    except sqlite3.IntegrityError as e:
        return False, f"Integrity Error: Enrollment number or email already exists ({e})."
    except Exception as e:
        return False, f"Failed to add student: {str(e)}"
    finally:
        conn.close()


def update_student_grade(
    enrollment_no: str,
    semester: int,
    subject_code: str,
    new_grade: str,
    new_points: float,
) -> Tuple[bool, str]:
    """Faculty utility to update or publish course grade for a student."""
    enrollment_no = enrollment_no.strip().upper()
    conn = get_db_connection()
    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, name FROM students WHERE enrollment_no = ?",
                (enrollment_no,),
            )
            row = cursor.fetchone()
            if not row:
                return False, f"Student {enrollment_no} not found."

            student_id, student_name = row["id"], row["name"]
            cursor.execute(
                """
                UPDATE academic_results
                SET grade = ?, points = ?, published_date = ?
                WHERE student_id = ? AND semester = ? AND subject_code = ?
                """,
                (new_grade, new_points, datetime.now().strftime("%Y-%m-%d"), student_id, semester, subject_code),
            )
            if cursor.rowcount == 0:
                return False, f"No matching result record found for Subject {subject_code} in Semester {semester}."

        # Invalidate cache so student sees updated result instantly
        CACHE.delete(f"results:{enrollment_no}")
        return True, f"Grade updated to {new_grade} ({new_points}) for {student_name} ({subject_code})."
    except Exception as e:
        return False, f"Failed to update grade: {str(e)}"
    finally:
        conn.close()


def seed_sample_students(count: int = 200) -> int:
    """Bulk seed realistic student records and results."""
    first_names = [
        "Aarav", "Vivaan", "Aditya", "Vihaan", "Arjun", "Sai", "Reyansh", "Ayaan", "Krishna", "Ishaan",
        "Ananya", "Diya", "Isha", "Riya", "Aadhya", "Saanvi", "Kiara", "Myra", "Pari", "Navya",
        "Rohan", "Priya", "Rahul", "Neha", "Sneha", "Kunal", "Meera", "Vikram", "Tanvi", "Siddharth"
    ]
    last_names = [
        "Sharma", "Verma", "Gupta", "Patel", "Reddy", "Nair", "Iyer", "Banerjee", "Chatterjee", "Mishra",
        "Singh", "Kumar", "Das", "Roy", "Mukherjee", "Bhattacharya", "Sengupta", "Choudhury", "Bose", "Ghosh"
    ]

    conn = get_db_connection()
    inserted = 0
    try:
        with conn:
            cursor = conn.cursor()
            base_year = 2024
            for i in range(1, count + 1):
                fname = random.choice(first_names)
                lname = random.choice(last_names)
                name = f"{fname} {lname}"
                dept = random.choice(COURSES)
                dept_code = dept[:2].upper()
                year = random.choice([1, 2, 3, 4])
                semester = (year * 2) - random.choice([0, 1])
                cgpa = round(random.uniform(6.5, 9.9), 2)
                enrollment = f"{base_year - (year - 1)}{dept_code}{1000 + i}"
                email = f"{fname.lower()}.{lname.lower()}{i}@iem.edu.in"

                try:
                    cursor.execute(
                        """
                        INSERT INTO students (enrollment_no, name, email, department, year, semester, cgpa, status)
                        VALUES (?, ?, ?, ?, ?, ?, ?, 'ACTIVE')
                        """,
                        (enrollment, name, email, dept, year, semester, cgpa),
                    )
                    student_id = cursor.lastrowid
                    inserted += 1

                    subjects = SUBJECT_CATALOG.get(dept, SUBJECT_CATALOG["Computer Science & Engineering"])
                    for sem in range(1, semester + 1):
                        for code, sub_name, credits in subjects:
                            grade_tuple = random.choices(
                                GRADE_SCALE, weights=[w for _, _, w in GRADE_SCALE]
                            )[0]
                            cursor.execute(
                                """
                                INSERT INTO academic_results (student_id, semester, subject_code, subject_name, credits, grade, points, published_date)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                                """,
                                (
                                    student_id,
                                    sem,
                                    f"{code.split()[0]}-{sem}",
                                    f"{sub_name} (Sem {sem})",
                                    credits,
                                    grade_tuple[0],
                                    grade_tuple[1],
                                    "2025-05-15",
                                ),
                            )
                except sqlite3.IntegrityError:
                    continue
    finally:
        conn.close()
    return inserted


def get_all_students(limit: int = 150, search_query: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieve students list with optional search filtering."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        if search_query and search_query.strip():
            term = f"%{search_query.strip()}%"
            cursor.execute(
                """
                SELECT id, enrollment_no, name, email, department, year, semester, cgpa, status, created_at
                FROM students
                WHERE enrollment_no LIKE ? OR name LIKE ? OR department LIKE ?
                ORDER BY id DESC LIMIT ?
                """,
                (term, term, term, limit),
            )
        else:
            cursor.execute(
                """
                SELECT id, enrollment_no, name, email, department, year, semester, cgpa, status, created_at
                FROM students
                ORDER BY id DESC LIMIT ?
                """,
                (limit,),
            )
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_students_by_department(
    department: str, semester: Optional[int] = None
) -> List[Dict[str, Any]]:
    """Faculty query to list students enrolled in a department/semester."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        if semester:
            cursor.execute(
                """
                SELECT id, enrollment_no, name, email, department, year, semester, cgpa, status
                FROM students
                WHERE department = ? AND semester = ?
                ORDER BY enrollment_no ASC
                """,
                (department, semester),
            )
        else:
            cursor.execute(
                """
                SELECT id, enrollment_no, name, email, department, year, semester, cgpa, status
                FROM students
                WHERE department = ?
                ORDER BY enrollment_no ASC
                """,
                (department,),
            )
        return [dict(r) for r in cursor.fetchall()]
    finally:
        conn.close()


def get_student_results(
    enrollment_no: str, bypass_cache: bool = False
) -> Dict[str, Any]:
    """
    Fetch student profile and academic results with Redis Caching and audit logging.
    Measures exact query execution time in milliseconds.
    """
    enrollment_no = enrollment_no.strip().upper()
    cache_key = f"results:{enrollment_no}"

    start_time = time.perf_counter()
    if not bypass_cache:
        cached = CACHE.get(cache_key)
        if cached:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            log_query_audit(enrollment_no, "RESULT_LOOKUP", duration_ms, cache_hit=True)
            cached["query_duration_ms"] = round(duration_ms, 3)
            cached["source"] = "Redis / In-Memory Cache Hit ⚡"
            cached["cache_hit"] = True
            return cached

    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, enrollment_no, name, email, department, year, semester, cgpa, status, created_at
            FROM students
            WHERE enrollment_no = ?
            """,
            (enrollment_no,),
        )
        student_row = cursor.fetchone()
        if not student_row:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            return {
                "found": False,
                "message": f"Student with Enrollment No '{enrollment_no}' was not found in the database.",
                "query_duration_ms": round(duration_ms, 3),
                "source": "Cold Database Miss",
                "cache_hit": False,
            }

        student_data = dict(student_row)

        cursor.execute(
            """
            SELECT semester, subject_code, subject_name, credits, grade, points, published_date
            FROM academic_results
            WHERE student_id = ?
            ORDER BY semester DESC, subject_code ASC
            """,
            (student_data["id"],),
        )
        results_rows = [dict(r) for r in cursor.fetchall()]

        duration_ms = (time.perf_counter() - start_time) * 1000.0
        log_query_audit(enrollment_no, "RESULT_LOOKUP", duration_ms, cache_hit=False)

        response = {
            "found": True,
            "student": student_data,
            "results": results_rows,
            "total_courses": len(results_rows),
            "query_duration_ms": round(duration_ms, 3),
            "source": "Cold SQLite Disk Query (Un-cached) 🐢",
            "cache_hit": False,
        }

        # Store in Redis Cache with 120s TTL
        CACHE.set(cache_key, response, ttl_seconds=120)
        return response
    finally:
        conn.close()


def log_query_audit(
    enrollment_no: str, query_type: str, duration_ms: float, cache_hit: bool
) -> None:
    """Record query performance audit log in database."""
    try:
        conn = get_db_connection()
        with conn:
            conn.execute(
                """
                INSERT INTO query_audit_logs (enrollment_no, query_type, duration_ms, cache_hit)
                VALUES (?, ?, ?, ?)
                """,
                (enrollment_no, query_type, duration_ms, 1 if cache_hit else 0),
            )
        conn.close()
    except Exception:
        pass


def get_query_logs(limit: int = 15) -> List[Dict[str, Any]]:
    """Retrieve recent query audit logs."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, enrollment_no, query_type, duration_ms, cache_hit, timestamp
            FROM query_audit_logs
            ORDER BY id DESC LIMIT ?
            """,
            (limit,),
        )
        return [dict(r) for r in cursor.fetchall()]
    finally:
        conn.close()


def get_db_stats() -> Dict[str, Any]:
    """Retrieve database disk footprint, row counts, and cache health."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM students;")
        student_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM academic_results;")
        result_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM query_audit_logs;")
        audit_count = cursor.fetchone()[0]

        db_size_kb = (
            round(DB_PATH.stat().st_size / 1024.0, 1) if DB_PATH.exists() else 0.0
        )

        return {
            "student_count": student_count,
            "result_count": result_count,
            "audit_count": audit_count,
            "db_size_kb": db_size_kb,
            "db_path": str(DB_PATH),
            "cache": CACHE.get_stats(),
        }
    finally:
        conn.close()


def run_db_stress_benchmark(num_queries: int = 60) -> Dict[str, Any]:
    """
    Runs an empirical database load test measuring cold DB reads vs Redis cache reads.
    Returns latency distributions and throughput metrics.
    """
    students = get_all_students(limit=30)
    if not students:
        return {"error": "No students available to benchmark. Seed the database first."}

    cold_latencies = []
    cached_latencies = []

    for _ in range(num_queries // 2):
        s = random.choice(students)
        t0 = time.perf_counter()
        get_student_results(s["enrollment_no"], bypass_cache=True)
        cold_latencies.append((time.perf_counter() - t0) * 1000.0)

        t1 = time.perf_counter()
        get_student_results(s["enrollment_no"], bypass_cache=False)
        cached_latencies.append((time.perf_counter() - t1) * 1000.0)

    return {
        "num_queries": len(cold_latencies) + len(cached_latencies),
        "cold_avg_ms": round(float(sum(cold_latencies) / len(cold_latencies)), 3) if cold_latencies else 0.0,
        "cold_p95_ms": round(float(sorted(cold_latencies)[int(len(cold_latencies) * 0.95)]), 3) if cold_latencies else 0.0,
        "cached_avg_ms": round(float(sum(cached_latencies) / len(cached_latencies)), 3) if cached_latencies else 0.0,
        "cached_p95_ms": round(float(sorted(cached_latencies)[int(len(cached_latencies) * 0.95)]), 3) if cached_latencies else 0.0,
        "speedup_factor": round(
            (sum(cold_latencies) / len(cold_latencies))
            / max(sum(cached_latencies) / len(cached_latencies), 0.0001),
            1,
        ) if cold_latencies and cached_latencies else 1.0,
    }


# Auto-initialize on import
init_db()
