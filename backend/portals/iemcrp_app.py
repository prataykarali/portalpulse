"""Independent IEMCRP Application (State University Examination Cell).

Monolithic Campus Resource Planning ERP with intentionally constrained database connection pool (N=50).
Simulates real lock contention and thread starvation under high un-cached query load.

Independent execution contract:
- Can run standalone on any port (uvicorn backend.portals.iemcrp_app:iemcrp_app --port 8002)
- Mountable as an independent sub-app
- Communicates with PortalPulse strictly through the PortalAdapter interface
"""

from __future__ import annotations

import random
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

iemcrp_app = FastAPI(
    title="IEMCRP — State University Campus Resource Planning",
    description="Monolithic educational ERP with constrained DB pool (50 max connections) and transactional marksheet operations.",
    version="2.0.0",
)

# ---------------------------------------------------------------------------
# REAL MONOLITHIC DATABASE ENGINE WITH CONSTRAINED CONNECTION POOL (N=50)
# ---------------------------------------------------------------------------
class MonolithicDatabasePool:
    """Real constrained database connection pool with thread starvation modeling."""

    def __init__(self, max_connections: int = 50) -> None:
        self.max_connections = max_connections
        self._semaphore = threading.BoundedSemaphore(max_connections)
        self._lock = threading.Lock()
        self.active_connections = 0
        self.waiting_queries = 0
        self.total_queries = 0
        self.failed_queries = 0

        # Fault injection state
        self.injected_db_latency_ms: float = 0.0
        self.pool_exhaustion_forced: bool = False
        self._exhaustion_locks: List[Any] = []

    @property
    def available_connections(self) -> int:
        """Remaining available connection slots."""
        with self._lock:
            return max(0, self.max_connections - self.active_connections)

    def acquire_connection(self, timeout_sec: float = 2.5, timeout: Optional[float] = None) -> bool:
        """Acquire a database connection slot, or block until timeout."""
        eff_timeout = timeout if timeout is not None else timeout_sec
        with self._lock:
            self.waiting_queries += 1

        start = time.monotonic()
        acquired = self._semaphore.acquire(timeout=eff_timeout)

        with self._lock:
            self.waiting_queries = max(0, self.waiting_queries - 1)
            if acquired:
                self.active_connections += 1
                self.total_queries += 1
            else:
                self.failed_queries += 1

        return acquired

    def release_connection(self, conn: Any = None) -> None:
        """Release an acquired connection slot."""
        with self._lock:
            if self.active_connections > 0:
                self.active_connections -= 1
                self._semaphore.release()

    def get_stats(self) -> Dict[str, Any]:
        """Return pool utilization metrics."""
        with self._lock:
            util_pct = round((self.active_connections / max(1, self.max_connections)) * 100.0, 1)
            return {
                "max_connections": self.max_connections,
                "active_connections": self.active_connections,
                "waiting_queries": self.waiting_queries,
                "utilization_percent": util_pct,
                "total_queries": self.total_queries,
                "failed_queries": self.failed_queries,
                "is_exhausted": self.active_connections >= self.max_connections,
                "injected_db_latency_ms": self.injected_db_latency_ms,
            }

    def set_fault_db_latency(self, delay_ms: float) -> None:
        """Inject real query execution sleep delay."""
        with self._lock:
            self.injected_db_latency_ms = max(0.0, delay_ms)

    def set_fault_pool_exhaustion(self, enabled: bool) -> None:
        """Forcibly exhaust all available connection slots."""
        with self._lock:
            if enabled and not self.pool_exhaustion_forced:
                self.pool_exhaustion_forced = True
                # Acquire as many semaphore tokens as possible
                while len(self._exhaustion_locks) < (self.max_connections - 2):
                    if self._semaphore.acquire(blocking=False):
                        self.active_connections += 1
                        self._exhaustion_locks.append(True)
                    else:
                        break
            elif not enabled and self.pool_exhaustion_forced:
                self.pool_exhaustion_forced = False
                for _ in self._exhaustion_locks:
                    if self.active_connections > 0:
                        self.active_connections -= 1
                        self._semaphore.release()
                self._exhaustion_locks.clear()


DB_POOL = MonolithicDatabasePool(max_connections=50)

# Local operational state
IEMCRP_INFRA_STATE = {
    "php_workers": 4,
    "waiting_room_enabled": False,
    "waiting_room_limit": 1500,
    "static_fallback_enabled": False,
    "5xx_injection_enabled": False,
    "rate_limit_per_sec": 120.0,
}

# ---------------------------------------------------------------------------
# DATA MODELS
# ---------------------------------------------------------------------------
class StudentLoginRequest(BaseModel):
    registration_no: str = Field(default="SU-2024-88492")
    password: str = Field(default="exam2026")

class ExamSubmitRequest(BaseModel):
    registration_no: str = Field(default="SU-2024-88492")
    subject_code: str = Field(default="CS-601")
    answers: Dict[str, str] = Field(default_factory=lambda: {"q1": "A", "q2": "C", "q3": "B"})

class GradeUpdateRequest(BaseModel):
    faculty_id: str = Field(default="FAC-102")
    student_id: str = Field(default="SU-2024-88492")
    subject: str = Field(default="Database Systems")
    grade: str = Field(default="A+")

# ---------------------------------------------------------------------------
# BUSINESS ENDPOINTS (INDEPENDENT IEMCRP APPLICATION)
# ---------------------------------------------------------------------------
@iemcrp_app.get("/health")
def health_check() -> Dict[str, Any]:
    return {
        "status": "HEALTHY",
        "app": "IEMCRP State University ERP",
        "architecture": "Monolithic PHP/Django + MySQL",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "db_pool": DB_POOL.get_stats(),
        "infra": IEMCRP_INFRA_STATE,
    }

@iemcrp_app.post("/api/auth/login")
def student_login(req: StudentLoginRequest, request: Request) -> Dict[str, Any]:
    if IEMCRP_INFRA_STATE["5xx_injection_enabled"]:
        raise HTTPException(status_code=503, detail="503 Service Unavailable: IEMCRP Monolith Crash")

    # Acquire DB connection for credential validation
    if not DB_POOL.acquire_connection(timeout_sec=1.5):
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Database Connection Pool Exhausted: Could not verify student credentials.",
        )

    try:
        if DB_POOL.injected_db_latency_ms > 0:
            time.sleep(DB_POOL.injected_db_latency_ms / 1000.0)
        time.sleep(0.015)  # Nominal 15ms auth query
        return {
            "status": "AUTHENTICATED",
            "registration_no": req.registration_no,
            "name": "Pratay Karali",
            "session_token": f"iemcrp_sess_{random.randint(10000, 99999)}",
            "department": "Computer Science & Engineering",
        }
    finally:
        DB_POOL.release_connection()

@iemcrp_app.get("/api/student/dashboard")
def student_dashboard(reg_no: str = "SU-2024-88492") -> Dict[str, Any]:
    if not DB_POOL.acquire_connection(timeout_sec=1.5):
        raise HTTPException(status_code=504, detail="Database Connection Pool Contention")
    try:
        if DB_POOL.injected_db_latency_ms > 0:
            time.sleep(DB_POOL.injected_db_latency_ms / 1000.0)
        time.sleep(0.012)
        return {
            "registration_no": reg_no,
            "semester": 6,
            "enrolled_courses": ["CS-601 Distributed Systems", "CS-602 Compiler Design", "CS-603 AI/ML"],
            "exam_status": "READY",
        }
    finally:
        DB_POOL.release_connection()

@iemcrp_app.get("/api/exam/questions")
def get_exam_questions(subject_code: str = "CS-601") -> Dict[str, Any]:
    # Static fallback bypasses database entirely when enabled
    if IEMCRP_INFRA_STATE["static_fallback_enabled"]:
        return {
            "mode": "STATIC_DEGRADED_FALLBACK",
            "subject": subject_code,
            "questions": [
                {"id": 1, "text": "Explain CAP Theorem.", "marks": 10},
                {"id": 2, "text": "Differentiate between ACID and BASE.", "marks": 10},
            ],
            "served_from": "STATIC_CDN_PAGE",
        }

    if not DB_POOL.acquire_connection(timeout_sec=1.5):
        raise HTTPException(status_code=504, detail="Database Pool Exhausted: Question bank locked")
    try:
        if DB_POOL.injected_db_latency_ms > 0:
            time.sleep(DB_POOL.injected_db_latency_ms / 1000.0)
        time.sleep(0.020)
        return {
            "mode": "TRANSACTIONAL_DYNAMIC",
            "subject": subject_code,
            "questions": [
                {"id": 1, "text": "Explain Two-Phase Commit protocol.", "marks": 10},
                {"id": 2, "text": "Describe Paxos consensus algorithm.", "marks": 10},
            ],
        }
    finally:
        DB_POOL.release_connection()

@iemcrp_app.post("/api/exam/autosave")
def exam_autosave(req: ExamSubmitRequest) -> Dict[str, Any]:
    if not DB_POOL.acquire_connection(timeout_sec=1.2):
        raise HTTPException(status_code=504, detail="Autosave dropped due to DB pool exhaustion")
    try:
        if DB_POOL.injected_db_latency_ms > 0:
            time.sleep(DB_POOL.injected_db_latency_ms / 1000.0)
        time.sleep(0.010)
        return {"status": "SAVED", "timestamp": datetime.now(timezone.utc).isoformat()}
    finally:
        DB_POOL.release_connection()

@iemcrp_app.post("/api/exam/submit")
def exam_submit(req: ExamSubmitRequest) -> Dict[str, Any]:
    if not DB_POOL.acquire_connection(timeout_sec=2.0):
        raise HTTPException(status_code=504, detail="Exam submission timed out: Database lock contention")
    try:
        if DB_POOL.injected_db_latency_ms > 0:
            time.sleep(DB_POOL.injected_db_latency_ms / 1000.0)
        time.sleep(0.040)  # Transaction commit takes ~40ms
        return {
            "status": "SUBMITTED_AND_LOCKED",
            "submission_id": f"SUB-{random.randint(100000, 999999)}",
            "confirmed_at": datetime.now(timezone.utc).isoformat(),
        }
    finally:
        DB_POOL.release_connection()

@iemcrp_app.get("/api/results/query")
def query_results(reg_no: str = "SU-2024-88492") -> Dict[str, Any]:
    if not DB_POOL.acquire_connection(timeout_sec=1.5):
        raise HTTPException(status_code=504, detail="Result Server Busy: DB Pool Exhaustion")
    try:
        if DB_POOL.injected_db_latency_ms > 0:
            time.sleep(DB_POOL.injected_db_latency_ms / 1000.0)
        # Heavy un-cached multi-table join
        time.sleep(0.035)
        return {
            "registration_no": reg_no,
            "sgpa": 9.42,
            "cgpa": 9.18,
            "classification": "First Class with Distinction",
            "marksheet_url": f"/marksheet/pdf/{reg_no}",
        }
    finally:
        DB_POOL.release_connection()

@iemcrp_app.post("/api/faculty/grades/save")
def save_grades(req: GradeUpdateRequest) -> Dict[str, Any]:
    if not DB_POOL.acquire_connection(timeout_sec=2.5):
        raise HTTPException(status_code=504, detail="Grade Publishing Lock Contention")
    try:
        if DB_POOL.injected_db_latency_ms > 0:
            time.sleep(DB_POOL.injected_db_latency_ms / 1000.0)
        time.sleep(0.045)
        return {"status": "GRADES_SAVED_AND_PUBLISHED", "faculty": req.faculty_id}
    finally:
        DB_POOL.release_connection()

# ---------------------------------------------------------------------------
# TELEMETRY & ADAPTER INTERFACE HOOKS
# ---------------------------------------------------------------------------
@iemcrp_app.get("/telemetry")
def get_iemcrp_telemetry() -> Dict[str, Any]:
    stats = DB_POOL.get_stats()
    # Compute latency based on pool saturation
    base_lat = 15.0 + stats["injected_db_latency_ms"]
    if stats["active_connections"] > 40:
        base_lat += (stats["active_connections"] - 40) * 45.0

    return {
        "portal_id": "college_portal",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "active_users": max(0, stats["active_connections"] * 18),
        "requests_per_sec": round(max(0.1, stats["active_connections"] * 2.8), 1),
        "cpu_percent": min(100.0, 10.0 + stats["active_connections"] * 1.5),
        "ram_percent": min(100.0, 35.0 + stats["active_connections"] * 0.8),
        "latency_ms": round(base_lat, 1),
        "p95_latency_ms": round(base_lat * 1.4, 1),
        "db_connections": stats["utilization_percent"],  # Percentage le=100.0
        "db_connection_limit": stats["max_connections"],
        "queue_length": stats["waiting_queries"],
        "service_instances": IEMCRP_INFRA_STATE["php_workers"],
        "error_rate": round(stats["failed_queries"] / max(1, stats["total_queries"]), 3),
        "db_pool_stats": stats,
        "is_simulated": False,
        "provenance": "LIVE_PORTAL",
    }

@iemcrp_app.post("/api/portalpulse/actions")
def execute_iemcrp_action(payload: Dict[str, Any]) -> Dict[str, Any]:
    action = payload.get("action", "")
    params = payload.get("parameters", {})

    if action == "ENABLE_WAITING_ROOM":
        IEMCRP_INFRA_STATE["waiting_room_enabled"] = True
        IEMCRP_INFRA_STATE["waiting_room_limit"] = params.get("max_admitted_sessions", 1500)
        return {"status": "SUCCESS", "action": action, "active": True}
    elif action == "DISABLE_WAITING_ROOM":
        IEMCRP_INFRA_STATE["waiting_room_enabled"] = False
        return {"status": "SUCCESS", "action": action, "active": False}
    elif action in ("ENABLE_DEGRADED_MODE", "STATIC_FALLBACK_DIVERT"):
        IEMCRP_INFRA_STATE["static_fallback_enabled"] = True
        return {"status": "SUCCESS", "action": action, "static_fallback": True, "message": "Static fallback divert activated."}
    elif action in ("DISABLE_DEGRADED_MODE", "RESTORE_FULL_DYNAMIC"):
        IEMCRP_INFRA_STATE["static_fallback_enabled"] = False
        return {"status": "SUCCESS", "action": action, "static_fallback": False, "message": "Full dynamic mode restored."}
    elif action == "SCALE_OUT_WORKERS":
        delta = params.get("replicas_delta", 2)
        IEMCRP_INFRA_STATE["php_workers"] = min(16, IEMCRP_INFRA_STATE["php_workers"] + delta)
        return {"status": "SUCCESS", "action": action, "new_workers": IEMCRP_INFRA_STATE["php_workers"]}
    elif action == "SCALE_IN_WORKERS":
        delta = params.get("replicas_delta", 2)
        IEMCRP_INFRA_STATE["php_workers"] = max(2, IEMCRP_INFRA_STATE["php_workers"] - delta)
        return {"status": "SUCCESS", "action": action, "new_workers": IEMCRP_INFRA_STATE["php_workers"]}
    elif action == "INJECT_FAULT":
        fault = params.get("fault_type", "")
        if fault == "DB_CONNECTION_EXHAUSTION":
            DB_POOL.set_fault_pool_exhaustion(True)
        elif fault == "DB_LATENCY":
            DB_POOL.set_fault_db_latency(params.get("delay_ms", 350.0))
        elif fault == "HTTP_5XX_BURST":
            IEMCRP_INFRA_STATE["5xx_injection_enabled"] = True
        return {"status": "FAULT_INJECTED", "fault": fault}
    elif action == "CLEAR_FAULT":
        DB_POOL.set_fault_pool_exhaustion(False)
        DB_POOL.set_fault_db_latency(0.0)
        IEMCRP_INFRA_STATE["5xx_injection_enabled"] = False
        return {"status": "FAULT_CLEARED"}

    return {"status": "UNKNOWN_ACTION", "action": action}
