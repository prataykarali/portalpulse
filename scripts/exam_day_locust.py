"""Exam Day High-Concurrency Multi-Persona & Multi-Portal Locust Load Generator.

Fulfills PRD-02:
- Targets both Nirantar (Railway ERP) and IEMCRP (Monolithic College ERP)
- 5 Realistic Personas with randomized think times & behaviors:
  1. StudentUser (50% weight): Normal linear student/passenger journey
  2. PanickedStudentUser (20% weight): Rapid refreshes (0.5-1.5s) & duplicate form submissions
  3. ResultRushStudentUser (15% weight): Massive concentrated bursts querying marksheet/trains
  4. FacultyUser (10% weight): Administrative roster checks & grade updates
  5. AbnormalBotUser (5% weight): High-rate scraping with zero think time
- 8 Traffic Modes:
  CONSTANT, RAMP_UP, RAMP_DOWN, SPIKE, WAVE, STAMPEDE, RESULT_RUSH, CUSTOM
"""

from __future__ import annotations

import os
import random
import time
from typing import Optional
from locust import HttpUser, LoadTestShape, between, task

TARGET_PORTAL = os.getenv("PORTAL_TARGET", "nirantar")  # "nirantar" or "college_portal"
TRAFFIC_MODE = os.getenv("TRAFFIC_MODE", "STAMPEDE")


# ===========================================================================
# 1. NORMAL STUDENT / PASSENGER USER (50% WEIGHT)
# ===========================================================================
class NormalStudentUser(HttpUser):
    """Standard user journey with authentic randomized think time (3–8s)."""

    weight = 50
    wait_time = between(3.0, 8.0)

    @task(3)
    def step1_browse_schedule_or_dashboard(self) -> None:
        sid = f"normal_{random.randint(1000, 9999)}"
        if TARGET_PORTAL == "college_portal":
            self.client.get(
                "/portals/college/api/student/dashboard?reg_no=SU-2024-88492",
                headers={"X-Session-ID": sid},
            )
        else:
            self.client.get(
                "/portals/nirantar/api/trains/search?source=NDLS&destination=BPL",
                headers={"X-Session-ID": sid},
            )

    @task(2)
    def step2_view_exam_or_train(self) -> None:
        sid = f"normal_{random.randint(1000, 9999)}"
        if TARGET_PORTAL == "college_portal":
            self.client.get(
                "/portals/college/api/exam/questions?subject_code=CS-601",
                headers={"X-Session-ID": sid},
            )
        else:
            self.client.get(
                "/portals/nirantar/api/health",
                headers={"X-Session-ID": sid},
            )

    @task(1)
    def step3_submit_or_book(self) -> None:
        sid = f"normal_{random.randint(1000, 9999)}"
        if TARGET_PORTAL == "college_portal":
            self.client.post(
                "/portals/college/api/exam/submit",
                json={"registration_no": "SU-2024-88492", "subject_code": "CS-601", "answers": {"q1": "A", "q2": "C"}},
                headers={"X-Session-ID": sid},
            )
        else:
            self.client.post(
                "/portals/nirantar/api/booking/tatkal",
                json={"train_number": "12001", "passenger_name": "Student Normal", "quota": "TATKAL"},
                headers={"X-Session-ID": sid},
            )


# ===========================================================================
# 2. PANICKED STUDENT USER (20% WEIGHT)
# ===========================================================================
class PanickedStudentUser(HttpUser):
    """Impatient user hammering refresh and duplicate clicks (0.5–1.5s wait)."""

    weight = 20
    wait_time = between(0.5, 1.5)

    @task(4)
    def frantic_refresh(self) -> None:
        sid = f"panic_{random.randint(10, 80)}"
        if TARGET_PORTAL == "college_portal":
            self.client.get(
                f"/portals/college/api/student/dashboard?reg_no=SU-2024-88492&rand={random.randint(1, 99999)}",
                headers={"X-Session-ID": sid, "Cache-Control": "no-cache"},
            )
        else:
            self.client.get(
                f"/portals/nirantar/api/trains/search?source=HWH&destination=NDLS&rand={random.randint(1, 99999)}",
                headers={"X-Session-ID": sid, "Cache-Control": "no-cache"},
            )

    @task(2)
    def duplicate_form_submit(self) -> None:
        sid = f"panic_{random.randint(10, 80)}"
        if TARGET_PORTAL == "college_portal":
            self.client.post(
                "/portals/college/api/exam/submit",
                json={"registration_no": "SU-2024-88492", "subject_code": "CS-601"},
                headers={"X-Session-ID": sid},
            )
        else:
            self.client.post(
                "/portals/nirantar/api/booking/tatkal",
                json={"train_number": "12301", "passenger_name": "Panicked Applicant", "quota": "TATKAL"},
                headers={"X-Session-ID": sid},
            )


# ===========================================================================
# 3. RESULT RUSH STUDENT USER (15% WEIGHT)
# ===========================================================================
class ResultRushStudentUser(HttpUser):
    """Massive concentrated rush on score retrieval & marksheet lookups."""

    weight = 15
    wait_time = between(1.0, 2.5)

    @task
    def lookup_results_burst(self) -> None:
        sid = f"rush_{random.randint(100, 999)}"
        if TARGET_PORTAL == "college_portal":
            self.client.get(
                f"/portals/college/api/results/query?reg_no=SU-2024-{random.randint(10000, 99999)}",
                headers={"X-Session-ID": sid},
            )
        else:
            self.client.get(
                f"/portals/nirantar/api/trains/search?date=2026-09-15&seat=TATKAL&burst={random.randint(1, 10000)}",
                headers={"X-Session-ID": sid},
            )


# ===========================================================================
# 4. FACULTY / ADMIN USER (10% WEIGHT)
# ===========================================================================
class FacultyUser(HttpUser):
    """Faculty publishing grade updates or checking train rosters."""

    weight = 10
    wait_time = between(4.0, 10.0)

    @task(2)
    def check_roster(self) -> None:
        sid = f"fac_{random.randint(1, 30)}"
        if TARGET_PORTAL == "college_portal":
            self.client.get("/portals/college/api/student/dashboard", headers={"X-Session-ID": sid})
        else:
            self.client.get("/portals/nirantar/api/trains/search", headers={"X-Session-ID": sid})

    @task(1)
    def save_and_invalidate(self) -> None:
        sid = f"fac_{random.randint(1, 30)}"
        if TARGET_PORTAL == "college_portal":
            self.client.post(
                "/portals/college/api/faculty/grades/save",
                json={"faculty_id": "FAC-102", "student_id": f"SU-2024-{random.randint(1000, 9999)}", "grade": "A+"},
                headers={"X-Session-ID": sid},
            )
        else:
            self.client.get("/portals/nirantar/api/health", headers={"X-Session-ID": sid})


# ===========================================================================
# 5. ABNORMAL CLIENT / SCRAPING BOT (5% WEIGHT)
# ===========================================================================
class AbnormalBotUser(HttpUser):
    """Aggressive bot crawler hitting endpoints with zero/minimal think time."""

    weight = 5
    wait_time = between(0.1, 0.3)

    @task
    def probe_rapid(self) -> None:
        sid = f"bot_{random.randint(1, 10)}"
        headers = {"User-Agent": "BotNet-ResilienceTest/3.0", "X-Session-ID": sid}
        if TARGET_PORTAL == "college_portal":
            self.client.get("/portals/college/api/results/query?reg_no=BOT-EXAM", headers=headers)
        else:
            self.client.get("/portals/nirantar/api/trains/search?probe=1", headers=headers)


# ===========================================================================
# 6. TRAFFIC SHAPE CONTROLLER (8 TRAFFIC MODES)
# ===========================================================================
class MultiModeLoadShape(LoadTestShape):
    """Locust custom load shape supporting all 8 PRD-02 traffic modes."""

    def get_stages(self) -> list[dict]:
        mode = TRAFFIC_MODE.upper()
        if mode == "CONSTANT":
            return [{"duration": 180, "users": 1200, "spawn_rate": 100}]
        elif mode == "RAMP_UP":
            return [
                {"duration": 45, "users": 500, "spawn_rate": 50},
                {"duration": 90, "users": 1500, "spawn_rate": 100},
                {"duration": 150, "users": 3500, "spawn_rate": 150},
                {"duration": 200, "users": 6000, "spawn_rate": 200},
            ]
        elif mode == "RAMP_DOWN":
            return [
                {"duration": 40, "users": 4000, "spawn_rate": 200},
                {"duration": 90, "users": 2000, "spawn_rate": 100},
                {"duration": 140, "users": 500, "spawn_rate": 50},
            ]
        elif mode == "SPIKE":
            return [
                {"duration": 30, "users": 400, "spawn_rate": 50},
                {"duration": 60, "users": 7500, "spawn_rate": 500},  # Sharp immediate spike
                {"duration": 120, "users": 800, "spawn_rate": 200},
            ]
        elif mode == "WAVE":
            return [
                {"duration": 30, "users": 500, "spawn_rate": 50},
                {"duration": 60, "users": 3500, "spawn_rate": 200},
                {"duration": 90, "users": 800, "spawn_rate": 150},
                {"duration": 120, "users": 4500, "spawn_rate": 250},
                {"duration": 150, "users": 1000, "spawn_rate": 150},
            ]
        elif mode == "RESULT_RUSH":
            return [
                {"duration": 20, "users": 800, "spawn_rate": 100},
                {"duration": 80, "users": 9000, "spawn_rate": 400},
                {"duration": 140, "users": 2000, "spawn_rate": 200},
            ]
        elif mode == "CUSTOM":
            custom_users = int(os.getenv("CUSTOM_USERS", "2000"))
            custom_dur = int(os.getenv("CUSTOM_DURATION", "120"))
            return [{"duration": custom_dur, "users": custom_users, "spawn_rate": 100}]
        else:
            # Default STAMPEDE mode
            return [
                {"duration": 30, "users": 500, "spawn_rate": 50},    # Baseline
                {"duration": 60, "users": 2500, "spawn_rate": 150},  # Normal exam flow
                {"duration": 100, "users": 5500, "spawn_rate": 250}, # Stampede surge
                {"duration": 140, "users": 8000, "spawn_rate": 300}, # Peak capacity test
                {"duration": 180, "users": 1500, "spawn_rate": 150}, # Post-action recovery
            ]

    def tick(self) -> Optional[tuple[int, float]]:
        run_time = self.get_run_time()
        for stage in self.get_stages():
            if run_time < stage["duration"]:
                return stage["users"], float(stage["spawn_rate"])
        return None
