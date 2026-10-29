"""PortalPulse Continuous Autonomous Traffic Controller & Real Load Generator.

Fulfills Module 3 Requirements:
- Drives continuous realistic result-day traffic against actual IEMCRP endpoints.
- Reuses 5 authentic personas:
  1. NormalStudentUser (50%)
  2. PanickedStudentUser (20%)
  3. ResultRushStudentUser (15%)
  4. FacultyUser (10%)
  5. AbnormalBotUser (5%)
- Manages an eight-phase continuous run or a twelve-case local demo, including
  DB saturation, rate limiting, gateway failures, recovery, and a second wave.
- Distinguishes REAL REQUEST LOAD from VIRTUAL USER SCENARIO SCALE (50 to 12,500 VUs).
- Continuous transaction accounting for:
  - GET dashboard
  - GET exam questions
  - POST exam submit
  - GET results
  - POST faculty grades
- Rolling transaction buffer and queryable REST API.
"""

from __future__ import annotations

import asyncio
import collections
import logging
import os
import random
import threading
import time
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

import httpx
import numpy as np
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from backend.portals.iemcrp_app import DB_POOL, IEMCRP_INFRA_STATE, iemcrp_app

logger = logging.getLogger("portalpulse.traffic_controller")

DEMO_MAX_WORKERS = 6
DEMO_MAX_REQUESTS_PER_SECOND = 12.0
DEMO_MAX_RUNTIME_SECONDS = 100.0
DEMO_START_TEMPERATURE_C = 85.0
DEMO_STOP_TEMPERATURE_C = 88.0


def cpu_package_temperature_c() -> Optional[float]:
    """Read the package sensor when the host exposes one; unknown stays unknown."""
    try:
        import psutil
        readings = psutil.sensors_temperatures().get("coretemp", [])
        package = next((entry.current for entry in readings if "Package" in entry.label), None)
        return float(package) if package is not None else None
    except (ImportError, OSError, ValueError, AttributeError):
        return None


# ===========================================================================
# 1. SCHEMAS AND DATA MODELS
# ===========================================================================
class TrafficPhase(str, Enum):
    BASELINE = "BASELINE"
    RAMP = "RAMP"
    RESULT_RUSH = "RESULT_RUSH"
    SATURATION = "SATURATION"
    ANOMALY_DETECTION = "ANOMALY_DETECTION"
    POLICY_ACTION = "POLICY_ACTION"
    CONTROLLED_RECOVERY = "CONTROLLED_RECOVERY"
    RATE_LIMIT_PRESSURE = "RATE_LIMIT_PRESSURE"
    GATEWAY_FAILURE = "GATEWAY_FAILURE"
    SUSTAINED_LOAD = "SUSTAINED_LOAD"
    SECOND_WAVE = "SECOND_WAVE"
    NORMAL = "NORMAL"


PHASE_SEQUENCE: List[TrafficPhase] = [
    TrafficPhase.BASELINE,
    TrafficPhase.RAMP,
    TrafficPhase.RESULT_RUSH,
    TrafficPhase.SATURATION,
    TrafficPhase.CONTROLLED_RECOVERY,
    TrafficPhase.SUSTAINED_LOAD,
    TrafficPhase.SECOND_WAVE,
    TrafficPhase.NORMAL,
]

DEMO_PHASE_SEQUENCE: List[TrafficPhase] = [
    TrafficPhase.BASELINE, TrafficPhase.RAMP, TrafficPhase.RESULT_RUSH,
    TrafficPhase.SATURATION, TrafficPhase.ANOMALY_DETECTION,
    TrafficPhase.POLICY_ACTION, TrafficPhase.CONTROLLED_RECOVERY,
    TrafficPhase.RATE_LIMIT_PRESSURE, TrafficPhase.GATEWAY_FAILURE,
    TrafficPhase.SUSTAINED_LOAD, TrafficPhase.SECOND_WAVE,
    TrafficPhase.NORMAL,
]

DEMO_PHASE_DURATIONS: Dict[TrafficPhase, float] = {
    TrafficPhase.BASELINE: 6.0, TrafficPhase.RAMP: 7.0,
    TrafficPhase.RESULT_RUSH: 8.0, TrafficPhase.SATURATION: 12.0,
    TrafficPhase.ANOMALY_DETECTION: 5.0, TrafficPhase.POLICY_ACTION: 5.0,
    TrafficPhase.CONTROLLED_RECOVERY: 8.0, TrafficPhase.RATE_LIMIT_PRESSURE: 7.0,
    TrafficPhase.GATEWAY_FAILURE: 7.0, TrafficPhase.SUSTAINED_LOAD: 7.0,
    TrafficPhase.SECOND_WAVE: 8.0, TrafficPhase.NORMAL: 6.0,
}

PHASE_SPECS: Dict[TrafficPhase, Dict[str, Any]] = {
    TrafficPhase.BASELINE: {
        "target_vus": 50,
        "duration_sec": 15.0,
        "real_workers": 4,
        "description": "Nominal student browsing before exam result release.",
    },
    TrafficPhase.RAMP: {
        "target_vus": 500,
        "duration_sec": 20.0,
        "real_workers": 12,
        "description": "Arrival ramp: Students logging in across university concourses.",
    },
    TrafficPhase.RESULT_RUSH: {
        "target_vus": 2500,
        "duration_sec": 25.0,
        "real_workers": 28,
        "description": "Result release stampede: High concurrent marksheet lookups.",
    },
    TrafficPhase.SATURATION: {
        "target_vus": 12500,
        "duration_sec": 30.0,
        "real_workers": 48,  # Contending on 50 max DB connections
        "description": "Extreme saturation knee-point: DB pool contention and queue backlogs.",
    },
    TrafficPhase.ANOMALY_DETECTION: {
        "target_vus": 12500, "duration_sec": 8.0, "real_workers": 48,
        "description": "Observe M2-M4 inference during measured IEMCRP saturation.",
    },
    TrafficPhase.POLICY_ACTION: {
        "target_vus": 10000, "duration_sec": 8.0, "real_workers": 40,
        "description": "Observe actual M5 recommendation, M6 safety, and M7 outcome.",
    },
    TrafficPhase.CONTROLLED_RECOVERY: {
        "target_vus": 5000,
        "duration_sec": 25.0,
        "real_workers": 20,
        "description": "Autonomous mitigation active: Virtual waiting room gating excess arrivals.",
    },
    TrafficPhase.RATE_LIMIT_PRESSURE: {
        "target_vus": 6500, "duration_sec": 16.0, "real_workers": 25,
        "description": "Refresh bursts meet the local ingress limit; HTTP 429s are measured.",
    },
    TrafficPhase.GATEWAY_FAILURE: {
        "target_vus": 4800, "duration_sec": 16.0, "real_workers": 22,
        "description": "A downstream failure causes measured 503 responses before recovery.",
    },
    TrafficPhase.SUSTAINED_LOAD: {
        "target_vus": 2500,
        "duration_sec": 25.0,
        "real_workers": 16,
        "description": "Sustainable post-mitigation operation within safe SLA bounds.",
    },
    TrafficPhase.SECOND_WAVE: {
        "target_vus": 5000,
        "duration_sec": 25.0,
        "real_workers": 32,
        "description": "Secondary rush of peer notifications and faculty grade confirmations.",
    },
    TrafficPhase.NORMAL: {
        "target_vus": 50,
        "duration_sec": 20.0,
        "real_workers": 4,
        "description": "Scenario completion: Gradual return to nominal baseline.",
    },
}


class TransactionRecord(BaseModel):
    """Immutable accounting entry for an individual HTTP transaction against IEMCRP."""

    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    persona: str
    endpoint: str
    status: int
    latency: float  # ms
    success: bool


class TrafficStatusResponse(BaseModel):
    """Real-time observability payload for GET /api/v1/traffic/status."""

    phase: str
    target_vus: int
    current_vus: int
    rps: float
    success_rate: float
    failure_rate: float
    p50: float
    p95: float
    p99: float
    elapsed: float
    scenario: str
    is_running: bool
    is_paused: bool
    real_requests_per_sec: float
    virtual_user_scale: int
    real_concurrency_workers: int
    in_flight_requests: int = 0
    scale_ratio: str
    stop_reason: Optional[str] = None


class StartTrafficRequest(BaseModel):
    scenario: str = Field(default="CONTINUOUS_RESULT_DAY")
    start_phase: TrafficPhase = Field(default=TrafficPhase.BASELINE)
    loop_continuously: bool = Field(default=True)


class SetScenarioRequest(BaseModel):
    phase: Optional[TrafficPhase] = None
    target_vus: Optional[int] = Field(default=None, ge=1, le=50000)
    duration_seconds: Optional[float] = Field(default=None, ge=1.0)
    scenario_name: Optional[str] = None


# ===========================================================================
# 2. THE FIVE REALISTIC PERSONAS
# ===========================================================================
class PersonaExecutor:
    name: str = "BasePersona"
    weight: int = 10

    @classmethod
    async def execute(
        cls, client: httpx.AsyncClient, record_cb: Any
    ) -> None:
        raise NotImplementedError

    @classmethod
    def get_think_time(cls) -> float:
        return 0.5


class NormalStudentPersona(PersonaExecutor):
    """Standard user journey with authentic randomized think time (0.2–0.8s in worker scale)."""

    name = "NormalStudentUser"
    weight = 50

    @classmethod
    async def execute(cls, client: httpx.AsyncClient, record_cb: Any) -> None:
        sid = f"normal_{random.randint(1000, 9999)}"
        roll = random.random()
        headers = {"X-Session-ID": sid}

        t0 = time.perf_counter()
        if roll < 0.50:
            ep = "GET /api/student/dashboard"
            reg = f"SU-2024-{random.randint(10000, 99999)}"
            res = await client.get(f"/api/student/dashboard?reg_no={reg}", headers=headers)
        elif roll < 0.83:
            ep = "GET /api/exam/questions"
            res = await client.get("/api/exam/questions?subject_code=CS-601", headers=headers)
        else:
            ep = "POST /api/exam/submit"
            payload = {
                "registration_no": f"SU-2024-{random.randint(10000, 99999)}",
                "subject_code": "CS-601",
                "answers": {"q1": "A", "q2": "C"},
            }
            res = await client.post("/api/exam/submit", json=payload, headers=headers)

        dur_ms = round((time.perf_counter() - t0) * 1000.0, 2)
        record_cb(
            TransactionRecord(
                persona=cls.name,
                endpoint=ep,
                status=res.status_code,
                latency=dur_ms,
                success=200 <= res.status_code < 400,
            )
        )

    @classmethod
    def get_think_time(cls) -> float:
        return random.uniform(0.15, 0.45)


class PanickedStudentPersona(PersonaExecutor):
    """Impatient user hammering refresh with no-cache and duplicate submissions."""

    name = "PanickedStudentUser"
    weight = 20

    @classmethod
    async def execute(cls, client: httpx.AsyncClient, record_cb: Any) -> None:
        sid = f"panic_{random.randint(10, 80)}"
        headers = {"X-Session-ID": sid, "Cache-Control": "no-cache"}

        t0 = time.perf_counter()
        if random.random() < 0.67:
            ep = "GET /api/student/dashboard"
            reg = f"SU-2024-{random.randint(10000, 99999)}"
            rand_val = random.randint(1, 999999)
            res = await client.get(f"/api/student/dashboard?reg_no={reg}&rand={rand_val}", headers=headers)
        else:
            ep = "POST /api/exam/submit"
            payload = {
                "registration_no": "SU-2024-88492",
                "subject_code": "CS-601",
            }
            res = await client.post("/api/exam/submit", json=payload, headers=headers)

        dur_ms = round((time.perf_counter() - t0) * 1000.0, 2)
        record_cb(
            TransactionRecord(
                persona=cls.name,
                endpoint=ep,
                status=res.status_code,
                latency=dur_ms,
                success=200 <= res.status_code < 400,
            )
        )

    @classmethod
    def get_think_time(cls) -> float:
        return random.uniform(0.04, 0.12)


class ResultRushStudentPersona(PersonaExecutor):
    """Massive concentrated rush on score retrieval & marksheet lookups."""

    name = "ResultRushStudentUser"
    weight = 15

    @classmethod
    async def execute(cls, client: httpx.AsyncClient, record_cb: Any) -> None:
        sid = f"rush_{random.randint(100, 999)}"
        reg = f"SU-2024-{random.randint(10000, 99999)}"
        ep = "GET /api/results/query"

        t0 = time.perf_counter()
        res = await client.get(f"/api/results/query?reg_no={reg}", headers={"X-Session-ID": sid})
        dur_ms = round((time.perf_counter() - t0) * 1000.0, 2)

        record_cb(
            TransactionRecord(
                persona=cls.name,
                endpoint=ep,
                status=res.status_code,
                latency=dur_ms,
                success=200 <= res.status_code < 400,
            )
        )

    @classmethod
    def get_think_time(cls) -> float:
        return random.uniform(0.05, 0.15)


class FacultyPersona(PersonaExecutor):
    """Faculty publishing grade updates or checking rosters."""

    name = "FacultyUser"
    weight = 10

    @classmethod
    async def execute(cls, client: httpx.AsyncClient, record_cb: Any) -> None:
        sid = f"fac_{random.randint(1, 30)}"
        headers = {"X-Session-ID": sid}

        t0 = time.perf_counter()
        if random.random() < 0.67:
            ep = "GET /api/student/dashboard"
            res = await client.get("/api/student/dashboard", headers=headers)
        else:
            ep = "POST /api/faculty/grades/save"
            payload = {
                "faculty_id": f"FAC-{random.randint(100, 110)}",
                "student_id": f"SU-2024-{random.randint(1000, 9999)}",
                "grade": "A+",
            }
            res = await client.post("/api/faculty/grades/save", json=payload, headers=headers)

        dur_ms = round((time.perf_counter() - t0) * 1000.0, 2)
        record_cb(
            TransactionRecord(
                persona=cls.name,
                endpoint=ep,
                status=res.status_code,
                latency=dur_ms,
                success=200 <= res.status_code < 400,
            )
        )

    @classmethod
    def get_think_time(cls) -> float:
        return random.uniform(0.25, 0.60)


class AbnormalBotPersona(PersonaExecutor):
    """Aggressive bot crawler hitting marksheet endpoints with near-zero think time."""

    name = "AbnormalBotUser"
    weight = 5

    @classmethod
    async def execute(cls, client: httpx.AsyncClient, record_cb: Any) -> None:
        sid = f"bot_{random.randint(1, 10)}"
        headers = {
            "User-Agent": "BotNet-ResilienceTest/3.0",
            "X-Session-ID": sid,
        }
        ep = "GET /api/results/query"

        t0 = time.perf_counter()
        res = await client.get("/api/results/query?reg_no=BOT-EXAM", headers=headers)
        dur_ms = round((time.perf_counter() - t0) * 1000.0, 2)

        record_cb(
            TransactionRecord(
                persona=cls.name,
                endpoint=ep,
                status=res.status_code,
                latency=dur_ms,
                success=200 <= res.status_code < 400,
            )
        )

    @classmethod
    def get_think_time(cls) -> float:
        return random.uniform(0.01, 0.04)


PERSONAS: List[type[PersonaExecutor]] = [
    NormalStudentPersona,
    PanickedStudentPersona,
    ResultRushStudentPersona,
    FacultyPersona,
    AbnormalBotPersona,
]
PERSONA_WEIGHTS: List[int] = [p.weight for p in PERSONAS]


# ===========================================================================
# 3. CONTINUOUS TRAFFIC CONTROLLER ENGINE
# ===========================================================================
class TrafficController:
    """Manages continuous phased traffic generation hitting real IEMCRP endpoints."""

    def __init__(self) -> None:
        self.is_running: bool = False
        self.is_paused: bool = False
        self.loop_continuously: bool = True
        self.scenario_name: str = "CONTINUOUS_RESULT_DAY"

        # Phase management
        self.current_phase_idx: int = 0
        self.phase_sequence: List[TrafficPhase] = PHASE_SEQUENCE
        self.current_phase: TrafficPhase = TrafficPhase.BASELINE
        self.phase_start_time: float = 0.0
        self.scenario_start_time: float = 0.0
        self.custom_phase_duration: Optional[float] = None
        self.custom_target_vus: Optional[int] = None

        # Virtual user tracking
        self.current_vus: int = 50
        self.target_vus: int = 50

        # Concurrency management
        self._supervisor_task: Optional[asyncio.Task] = None
        self._worker_tasks: List[asyncio.Task] = []
        self._active_worker_count: int = 0
        self.in_flight_requests: int = 0

        # Rolling accounting buffer
        self.transactions: collections.deque[TransactionRecord] = collections.deque(maxlen=2000)

        # Sliding window stats
        self.window_lock = asyncio.Lock()
        self.stats_p50: float = 18.0
        self.stats_p95: float = 35.0
        self.stats_p99: float = 65.0
        self.stats_rps: float = 0.0
        self.stats_success_rate: float = 100.0
        self.stats_failure_rate: float = 0.0
        self.arrival_factor: float = 1.0
        self._wave_target: float = 1.0
        self._last_wave_at: float = 0.0
        self._last_thermal_check: float = 0.0
        self.stop_reason: Optional[str] = None
        self._rate_lock = threading.Lock()
        self._next_request_at: float = 0.0
        self.last_started_at: Optional[float] = None

    def demo_restart_wait_seconds(self) -> float:
        """Limit repeat runs on a public demo host without slowing local use."""
        if os.getenv("PORTALPULSE_DEMO_MODE") != "1" or self.last_started_at is None:
            return 0.0
        try:
            cooldown = max(0.0, float(os.getenv("PORTALPULSE_DEMO_MIN_RESTART_SECONDS", "0")))
        except ValueError:
            cooldown = 0.0
        return max(0.0, cooldown - (time.monotonic() - self.last_started_at))

    def record_transaction(self, record: TransactionRecord) -> None:
        """Append to rolling transaction accounting buffer and stream via SSE."""
        self.transactions.append(record)
        try:
            from backend.streaming.broadcaster import STREAM_BROADCASTER

            STREAM_BROADCASTER.publish_transaction({
                "type": "transaction",
                "timestamp": record.timestamp,
                "persona": record.persona,
                "operation": record.endpoint,
                "endpoint": record.endpoint,
                "status_code": record.status,
                "duration_ms": record.latency,
                "success": record.success,
                "error": None if record.success else f"HTTP {record.status}",
            })
        except Exception:
            pass

    async def start(
        self,
        scenario: str = "CONTINUOUS_RESULT_DAY",
        start_phase: TrafficPhase = TrafficPhase.BASELINE,
        loop_continuously: bool = True,
    ) -> Dict[str, Any]:
        """Start or restart the continuous traffic generation engine."""
        if self.is_running and not self.is_paused:
            return {"status": "ALREADY_RUNNING", "phase": self.current_phase.value}

        restart_wait = self.demo_restart_wait_seconds()
        if restart_wait > 0:
            raise HTTPException(status_code=429, detail=f"Demo can restart in {restart_wait:.0f} seconds.")

        if os.getenv("PORTALPULSE_DEMO_MODE") == "1":
            temperature = cpu_package_temperature_c()
            if temperature is not None and temperature >= DEMO_START_TEMPERATURE_C:
                raise HTTPException(
                    status_code=503,
                    detail=f"Demo load held: CPU package is {temperature:.0f}°C; start allowed below {DEMO_START_TEMPERATURE_C:.0f}°C.",
                )

        self.scenario_name = scenario
        self.phase_sequence = DEMO_PHASE_SEQUENCE if scenario == "IEMCRP_RESULT_DAY_LIVE_DEMO" else PHASE_SEQUENCE
        self.loop_continuously = loop_continuously
        self.current_phase = start_phase
        self.current_phase_idx = (
            self.phase_sequence.index(start_phase) if start_phase in self.phase_sequence else 0
        )
        self.custom_phase_duration = None
        self.custom_target_vus = None

        now = time.monotonic()
        self.scenario_start_time = now
        self.last_started_at = now
        self.phase_start_time = now
        self.is_running = True
        self.is_paused = False
        self.arrival_factor = 1.0
        self._wave_target = 1.0
        self._last_wave_at = 0.0
        self._last_thermal_check = 0.0
        self._next_request_at = 0.0
        self.stop_reason = None

        # Start supervisor task
        if self._supervisor_task is None or self._supervisor_task.done():
            self._supervisor_task = asyncio.create_task(self._supervisor_loop())

        logger.info(f"[TRAFFIC_CONTROLLER] Started continuous scenario '{scenario}' at phase {self.current_phase.value}.")
        return {
            "status": "STARTED",
            "scenario": self.scenario_name,
            "phase": self.current_phase.value,
            "target_vus": self.get_phase_target_vus(),
        }

    async def stop(self) -> Dict[str, Any]:
        """Halt all traffic generation cleanly."""
        self.is_running = False
        self.is_paused = False

        if self._supervisor_task and not self._supervisor_task.done():
            self._supervisor_task.cancel()
            try:
                await self._supervisor_task
            except (asyncio.CancelledError, Exception):
                pass

        await self._adjust_workers(0)
        self.current_vus = 0
        self.stats_rps = 0.0
        self.stop_reason = self.stop_reason or "MANUAL_STOP"
        self._clear_demo_faults()

        logger.info("[TRAFFIC_CONTROLLER] Traffic controller stopped.")
        return {"status": "STOPPED", "scenario": self.scenario_name}

    def _clear_demo_faults(self) -> None:
        if os.getenv("PORTALPULSE_DEMO_MODE") != "1":
            return
        DB_POOL.set_fault_pool_exhaustion(False)
        DB_POOL.set_fault_db_latency(0)
        IEMCRP_INFRA_STATE["5xx_injection_enabled"] = False
        IEMCRP_INFRA_STATE["circuit_breaker_enabled"] = False
        IEMCRP_INFRA_STATE["rate_limit_per_sec"] = 120.0

    def pause(self) -> Dict[str, Any]:
        """Temporarily pause traffic generation without resetting phase."""
        if not self.is_running:
            return {"status": "NOT_RUNNING"}
        self.is_paused = True
        logger.info("[TRAFFIC_CONTROLLER] Traffic paused.")
        return {"status": "PAUSED", "phase": self.current_phase.value}

    def resume(self) -> Dict[str, Any]:
        """Resume paused traffic generation."""
        if not self.is_running:
            return {"status": "NOT_RUNNING"}
        self.is_paused = False
        logger.info("[TRAFFIC_CONTROLLER] Traffic resumed.")
        return {"status": "RESUMED", "phase": self.current_phase.value}

    def set_scenario(
        self,
        phase: Optional[TrafficPhase] = None,
        target_vus: Optional[int] = None,
        duration_seconds: Optional[float] = None,
        scenario_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Dynamically transition to a specific phase or customize parameters."""
        if scenario_name:
            self.scenario_name = scenario_name
        if phase:
            self.current_phase = phase
            self.current_phase_idx = (
                self.phase_sequence.index(phase) if phase in self.phase_sequence else 0
            )
            self.phase_start_time = time.monotonic()
        if target_vus is not None:
            self.custom_target_vus = target_vus
        if duration_seconds is not None:
            self.custom_phase_duration = duration_seconds

        logger.info(
            f"[TRAFFIC_CONTROLLER] Transitioned to phase={self.current_phase.value}, "
            f"target_vus={self.get_phase_target_vus()}, duration={self.get_phase_duration()}s."
        )
        return {
            "status": "UPDATED",
            "phase": self.current_phase.value,
            "target_vus": self.get_phase_target_vus(),
            "duration_seconds": self.get_phase_duration(),
        }

    def get_phase_target_vus(self) -> int:
        if self.custom_target_vus is not None:
            return self.custom_target_vus
        spec = PHASE_SPECS.get(self.current_phase, {})
        return spec.get("target_vus", 50)

    def get_phase_duration(self) -> float:
        if self.custom_phase_duration is not None:
            return self.custom_phase_duration
        if self.scenario_name == "IEMCRP_RESULT_DAY_LIVE_DEMO":
            return DEMO_PHASE_DURATIONS.get(self.current_phase, 10.0)
        spec = PHASE_SPECS.get(self.current_phase, {})
        return spec.get("duration_sec", 20.0)

    def get_phase_workers(self) -> int:
        spec = PHASE_SPECS.get(self.current_phase, {})
        return spec.get("real_workers", 4)

    # -----------------------------------------------------------------------
    # SUPERVISOR & WORKER COROUTINES
    # -----------------------------------------------------------------------
    async def _supervisor_loop(self) -> None:
        """Orchestrates phase progressions, smoothly ramps VUs, and tracks window stats."""
        while self.is_running:
            if os.getenv("PORTALPULSE_DEMO_MODE") == "1" and time.monotonic() - self.scenario_start_time >= DEMO_MAX_RUNTIME_SECONDS:
                self.is_running = False
                self.stop_reason = "TIME_LIMIT"
                await self._adjust_workers(0)
                self._clear_demo_faults()
                logger.info("[TRAFFIC_CONTROLLER] Local demo reached its 100-second safety limit.")
                break
            if os.getenv("PORTALPULSE_DEMO_MODE") == "1" and time.monotonic() - self._last_thermal_check >= 2.0:
                self._last_thermal_check = time.monotonic()
                temperature = cpu_package_temperature_c()
                if temperature is not None and temperature >= DEMO_STOP_TEMPERATURE_C:
                    self.is_running = False
                    self.stop_reason = f"THERMAL_LIMIT_{temperature:.0f}C"
                    await self._adjust_workers(0)
                    self._clear_demo_faults()
                    logger.warning("[TRAFFIC_CONTROLLER] Load stopped at %.1f°C package temperature.", temperature)
                    break
            if self.is_paused:
                await asyncio.sleep(0.5)
                continue

            now = time.monotonic()
            phase_elapsed = now - self.phase_start_time
            phase_duration = self.get_phase_duration()
            target_vus = self.get_phase_target_vus()

            # Smoothly interpolate current_vus towards target_vus
            if self.current_vus < target_vus:
                step = max(5, int((target_vus - self.current_vus) * 0.25))
                self.current_vus = min(target_vus, self.current_vus + step)
            elif self.current_vus > target_vus:
                step = max(5, int((self.current_vus - target_vus) * 0.25))
                self.current_vus = max(target_vus, self.current_vus - step)

            # Ensure proper number of real worker tasks are active
            # Demand waves alter the number and pace of real HTTP workers.
            # The UI only charts transactions observed after those requests run.
            if now - self._last_wave_at >= 2.0:
                spread = 0.22 if self.current_phase in (TrafficPhase.BASELINE, TrafficPhase.NORMAL) else 0.38
                self._wave_target = max(0.55, min(1.48, random.gauss(1.0, spread)))
                self._last_wave_at = now
            self.arrival_factor += (self._wave_target - self.arrival_factor) * 0.38
            worker_cap = DEMO_MAX_WORKERS if os.getenv("PORTALPULSE_DEMO_MODE") == "1" else 64
            desired_workers = max(2, min(worker_cap, round(self.get_phase_workers() * self.arrival_factor)))
            await self._adjust_workers(desired_workers)

            # Compute sliding-window statistics
            self._update_sliding_stats()

            # Broadcast real-time traffic status via SSE
            try:
                from backend.streaming.broadcaster import STREAM_BROADCASTER

                STREAM_BROADCASTER.publish_traffic({
                    "type": "traffic",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "scenario": self.scenario_name,
                    "phase": self.current_phase.value,
                    "phase_index": self.current_phase_idx,
                    "virtual_users": self.current_vus,
                    "target_vus": target_vus,
                    "active_workers": len(self._worker_tasks),
                    "total_requests": len(self.transactions),
                    "successful_requests": sum(1 for x in self.transactions if x.success),
                    "failed_requests": sum(1 for x in self.transactions if not x.success),
                    "error_rate": self.stats_failure_rate,
                    "rps": self.stats_rps,
                    "avg_latency_ms": round(sum(x.latency for x in self.transactions) / max(1, len(self.transactions)), 1),
                    "in_flight_requests": self.in_flight_requests,
                    "is_running": self.is_running,
                    "is_paused": self.is_paused,
                })
            except Exception:
                pass

            # Check if phase duration elapsed
            if phase_elapsed >= phase_duration:
                await self._advance_to_next_phase()

            await asyncio.sleep(0.5)

    async def _advance_to_next_phase(self) -> None:
        """Advance to the next phase in sequence or cycle back to BASELINE."""
        self.custom_phase_duration = None
        self.custom_target_vus = None
        self.current_phase_idx += 1

        if self.current_phase_idx >= len(self.phase_sequence):
            if self.loop_continuously:
                self.current_phase_idx = 0
            else:
                self.is_running = False
                self.stop_reason = "SCENARIO_COMPLETE"
                await self._adjust_workers(0)
                self._clear_demo_faults()
                logger.info("[TRAFFIC_CONTROLLER] Completed all scenario phases.")
                return

        self.current_phase = self.phase_sequence[self.current_phase_idx]
        if self.scenario_name == "IEMCRP_RESULT_DAY_LIVE_DEMO":
            if self.current_phase == TrafficPhase.SATURATION:
                DB_POOL.set_fault_db_latency(450)
                DB_POOL.set_fault_pool_exhaustion(True)
            elif self.current_phase == TrafficPhase.CONTROLLED_RECOVERY:
                DB_POOL.set_fault_pool_exhaustion(False)
                DB_POOL.set_fault_db_latency(0)
            elif self.current_phase == TrafficPhase.RATE_LIMIT_PRESSURE:
                IEMCRP_INFRA_STATE["rate_limit_per_sec"] = 4.0
            elif self.current_phase == TrafficPhase.GATEWAY_FAILURE:
                IEMCRP_INFRA_STATE["rate_limit_per_sec"] = 120.0
                IEMCRP_INFRA_STATE["5xx_injection_enabled"] = True
            elif self.current_phase == TrafficPhase.SUSTAINED_LOAD:
                IEMCRP_INFRA_STATE["5xx_injection_enabled"] = False
                IEMCRP_INFRA_STATE["circuit_breaker_enabled"] = False
                IEMCRP_INFRA_STATE["rate_limit_per_sec"] = 120.0
        self.phase_start_time = time.monotonic()
        logger.info(
            f"[TRAFFIC_CONTROLLER] Phase Transition: -> {self.current_phase.value} "
            f"(Target VUs: {self.get_phase_target_vus()})"
        )

    async def _adjust_workers(self, target_count: int) -> None:
        """Dynamically scale worker tasks to target count without crashing."""
        # Clean up done tasks
        self._worker_tasks = [t for t in self._worker_tasks if not t.done()]

        # Spawn new workers if needed
        while len(self._worker_tasks) < target_count and self.is_running:
            wid = len(self._worker_tasks)
            t = asyncio.create_task(self._worker_loop(wid))
            self._worker_tasks.append(t)

        # Cancel excess workers if target is lower
        cancelled = []
        while len(self._worker_tasks) > target_count:
            t = self._worker_tasks.pop()
            t.cancel()
            cancelled.append(t)

        if cancelled:
            await asyncio.gather(*cancelled, return_exceptions=True)

        self._active_worker_count = len(self._worker_tasks)

    async def _worker_loop(self, worker_id: int) -> None:
        """Individual worker coroutine executing authentic persona requests against IEMCRP."""
        transport = httpx.ASGITransport(app=iemcrp_app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test", timeout=3.5) as client:
            while self.is_running:
                if self.is_paused:
                    await asyncio.sleep(0.5)
                    continue

                try:
                    weights = {
                        TrafficPhase.RESULT_RUSH: [18, 30, 38, 8, 6],
                        TrafficPhase.SATURATION: [12, 35, 35, 8, 10],
                        TrafficPhase.RATE_LIMIT_PRESSURE: [12, 45, 25, 5, 13],
                        TrafficPhase.GATEWAY_FAILURE: [24, 26, 25, 10, 15],
                        TrafficPhase.SECOND_WAVE: [20, 30, 30, 15, 5],
                    }.get(self.current_phase, PERSONA_WEIGHTS)
                    persona_cls = random.choices(PERSONAS, weights=weights, k=1)[0]
                    if os.getenv("PORTALPULSE_DEMO_MODE") == "1":
                        with self._rate_lock:
                            slot = max(time.monotonic(), self._next_request_at)
                            self._next_request_at = slot + 1.0 / DEMO_MAX_REQUESTS_PER_SECOND
                        await asyncio.sleep(max(0.0, slot - time.monotonic()))
                        if not self.is_running:
                            break
                    self.in_flight_requests += 1
                    try:
                        await persona_cls.execute(client, self.record_transaction)
                    finally:
                        self.in_flight_requests -= 1
                    think_time = persona_cls.get_think_time() / max(0.55, self.arrival_factor)
                    await asyncio.sleep(think_time)
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.debug(f"[TRAFFIC_WORKER_{worker_id}] Error in worker execution: {e}")
                    await asyncio.sleep(0.2)

    def _update_sliding_stats(self) -> None:
        """Calculate p50, p95, p99, RPS, and success/failure rates from rolling buffer."""
        if not self.transactions:
            self.stats_p50 = 15.0
            self.stats_p95 = 28.0
            self.stats_p99 = 45.0
            self.stats_rps = 0.0
            self.stats_success_rate = 100.0
            self.stats_failure_rate = 0.0
            return

        # Use a real three-second accounting window.
        cutoff = datetime.now(timezone.utc).timestamp() - 3.0
        recent = [t for t in self.transactions if datetime.fromisoformat(t.timestamp).timestamp() >= cutoff]
        if not recent:
            self.stats_p50 = 0.0
            self.stats_p95 = 0.0
            self.stats_p99 = 0.0
            self.stats_rps = 0.0
            self.stats_success_rate = 100.0
            self.stats_failure_rate = 0.0
            return

        latencies = [t.latency for t in recent]
        successes = sum(1 for t in recent if t.success)
        total = len(recent)

        self.stats_p50 = round(float(np.percentile(latencies, 50)), 1)
        self.stats_p95 = round(float(np.percentile(latencies, 95)), 1)
        self.stats_p99 = round(float(np.percentile(latencies, 99)), 1)

        self.stats_success_rate = round((successes / max(1, total)) * 100.0, 1)
        self.stats_failure_rate = round(100.0 - self.stats_success_rate, 1)

        self.stats_rps = round(float(total) / 3.0, 1)

    def get_status(self) -> TrafficStatusResponse:
        """Return the current comprehensive traffic controller status."""
        elapsed = round(time.monotonic() - self.scenario_start_time, 1) if self.is_running else 0.0
        workers = max(1, self._active_worker_count)
        target_v = self.get_phase_target_vus()
        ratio_val = max(1, target_v // workers)

        return TrafficStatusResponse(
            phase=self.current_phase.value,
            target_vus=target_v,
            current_vus=self.current_vus if self.is_running else 0,
            rps=self.stats_rps,
            success_rate=self.stats_success_rate if self.is_running else 100.0,
            failure_rate=self.stats_failure_rate if self.is_running else 0.0,
            p50=self.stats_p50 if self.is_running else 0.0,
            p95=self.stats_p95 if self.is_running else 0.0,
            p99=self.stats_p99 if self.is_running else 0.0,
            elapsed=elapsed,
            scenario=self.scenario_name,
            is_running=self.is_running,
            is_paused=self.is_paused,
            real_requests_per_sec=self.stats_rps,
            virtual_user_scale=target_v,
            real_concurrency_workers=self._active_worker_count,
            in_flight_requests=self.in_flight_requests,
            scale_ratio=f"1 real request worker represents ~{ratio_val} conceptual virtual users",
            stop_reason=self.stop_reason,
        )

    def get_recent_transactions(self, limit: int = 50) -> List[TransactionRecord]:
        """Return rolling recent transactions for APM and dashboard inspection."""
        recent = list(self.transactions)
        return recent[-limit:] if recent else []


TRAFFIC_CONTROLLER = TrafficController()

# ===========================================================================
# 4. FASTAPI ROUTER & REST ENDPOINTS
# ===========================================================================
router = APIRouter(prefix="/api/v1/traffic", tags=["Autonomous Traffic Controller"])
alias_router = APIRouter(prefix="/traffic", tags=["Autonomous Traffic Controller"])


@router.post("/start", summary="Start Continuous Result-Day Scenario")
@alias_router.post("/start", summary="Start Continuous Result-Day Scenario")
async def start_traffic_endpoint(req: Optional[StartTrafficRequest] = None) -> Dict[str, Any]:
    req = req or StartTrafficRequest()
    return await TRAFFIC_CONTROLLER.start(
        scenario=req.scenario,
        start_phase=req.start_phase,
        loop_continuously=req.loop_continuously,
    )


@router.post("/stop", summary="Stop Traffic Generation")
@alias_router.post("/stop", summary="Stop Traffic Generation")
async def stop_traffic_endpoint() -> Dict[str, Any]:
    return await TRAFFIC_CONTROLLER.stop()


@router.post("/pause", summary="Pause Traffic Generation")
@alias_router.post("/pause", summary="Pause Traffic Generation")
def pause_traffic_endpoint() -> Dict[str, Any]:
    return TRAFFIC_CONTROLLER.pause()


@router.post("/resume", summary="Resume Traffic Generation")
@alias_router.post("/resume", summary="Resume Traffic Generation")
def resume_traffic_endpoint() -> Dict[str, Any]:
    return TRAFFIC_CONTROLLER.resume()


@router.post("/scenario", summary="Set Scenario or Override Phase")
@alias_router.post("/scenario", summary="Set Scenario or Override Phase")
def set_scenario_endpoint(req: SetScenarioRequest) -> Dict[str, Any]:
    return TRAFFIC_CONTROLLER.set_scenario(
        phase=req.phase,
        target_vus=req.target_vus,
        duration_seconds=req.duration_seconds,
        scenario_name=req.scenario_name,
    )


@router.get("/status", response_model=TrafficStatusResponse, summary="Get Live Traffic Engine Status")
@alias_router.get("/status", response_model=TrafficStatusResponse, summary="Get Live Traffic Engine Status")
def get_traffic_status_endpoint() -> TrafficStatusResponse:
    return TRAFFIC_CONTROLLER.get_status()


@router.get("/transactions", response_model=List[TransactionRecord], summary="Get Recent Transactions")
@alias_router.get("/transactions", response_model=List[TransactionRecord], summary="Get Recent Transactions")
def get_recent_transactions_endpoint(
    limit: int = Query(default=50, ge=1, le=500, description="Max transactions to return")
) -> List[TransactionRecord]:
    return TRAFFIC_CONTROLLER.get_recent_transactions(limit=limit)
