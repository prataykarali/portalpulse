"""Standard Locust Load Test Suite for PortalPulse Host Portals.

Defines 4 realistic personas with realistic think times and weighted journeys:
1. CasualVisitor (40%): Homepage -> View Details -> Leave (wait_time: 5-15s)
2. ActivePortalUser (40%): Session Auth -> Resources -> Telemetry (wait_time: 3-8s)
3. HeavyPowerUser (15%): Rapid queries across multiple endpoints (wait_time: 1-3s)
4. BackgroundApiUser (5%): Periodic healthchecks (wait_time: 5-10s)

Includes CapacitySteppedShape for stepped capacity benchmarking.
"""

from __future__ import annotations

import random
import uuid
from locust import HttpUser, LoadTestShape, between, task


class CasualVisitorUser(HttpUser):
    """Casual Visitor (40%): Browses homepage, inspects a page, and leaves."""

    weight = 40
    wait_time = between(5.0, 15.0)

    def on_start(self) -> None:
        self.session_id = f"sess_casual_{uuid.uuid4().hex[:12]}"
        self.headers = {"X-Session-ID": self.session_id, "User-Agent": "LocustCasualVisitor/1.0"}

    @task(3)
    def view_portal_home(self) -> None:
        self.client.get("/api/v1/portals/nirantar", headers=self.headers, name="[Visitor] Portal Home")

    @task(1)
    def view_capabilities(self) -> None:
        self.client.get(
            "/api/v1/portals/nirantar/capabilities",
            headers=self.headers,
            name="[Visitor] Capabilities",
        )


class ActivePortalUser(HttpUser):
    """Active User (40%): Authenticated session, inspects telemetry, queries resources."""

    weight = 40
    wait_time = between(3.0, 8.0)

    def on_start(self) -> None:
        self.auth_token = f"tok_active_{uuid.uuid4().hex[:16]}"
        self.headers = {
            "Authorization": f"Bearer {self.auth_token}",
            "User-Agent": "LocustActiveUser/2.0",
        }

    @task(3)
    def query_resources(self) -> None:
        self.client.get(
            "/api/v1/portals/nirantar/resources",
            headers=self.headers,
            name="[Active] Discovered Resources",
        )

    @task(2)
    def query_telemetry_history(self) -> None:
        self.client.get(
            "/api/v1/telemetry/nirantar/history",
            headers=self.headers,
            name="[Active] Telemetry Stream",
        )


class HeavyPowerUser(HttpUser):
    """Heavy Power User (15%): Rapid navigation, multiple tabs, short think times."""

    weight = 15
    wait_time = between(1.0, 3.0)

    def on_start(self) -> None:
        self.power_session = f"sess_power_{uuid.uuid4().hex[:12]}"
        self.headers = {
            "X-Session-ID": self.power_session,
            "User-Agent": "LocustPowerUser/3.0",
        }

    @task(4)
    def rapid_portal_catalog(self) -> None:
        self.client.get("/api/v1/portals", headers=self.headers, name="[Heavy] Portal Catalog")

    @task(2)
    def rapid_telemetry_sampling(self) -> None:
        self.client.get(
            "/api/v1/telemetry/nirantar/history",
            headers=self.headers,
            name="[Heavy] Rapid History Poll",
        )


class BackgroundApiUser(HttpUser):
    """Background API Traffic (5%): Healthchecks and status probes."""

    weight = 5
    wait_time = between(5.0, 10.0)

    @task
    def health_probe(self) -> None:
        self.client.get("/api/v1/portals/nirantar/health", name="[Background] Health Probe")


class CapacitySteppedShape(LoadTestShape):
    """Stepped load ramp discovering the degradation knee-point:
    Step 1: 100 VUs  (Normal day)
    Step 2: 500 VUs  (Busy midday)
    Step 3: 1,000 VUs (Peak hours)
    Step 4: 2,500 VUs (Surge begins, queue starts)
    Step 5: 5,000 VUs (Threshold boundary crossed)
    """

    stages = [
        {"duration": 30, "users": 100, "spawn_rate": 10},
        {"duration": 60, "users": 500, "spawn_rate": 25},
        {"duration": 90, "users": 1000, "spawn_rate": 50},
        {"duration": 120, "users": 2500, "spawn_rate": 100},
        {"duration": 150, "users": 5000, "spawn_rate": 200},
    ]

    def tick(self) -> tuple[int, float] | None:
        run_time = self.get_run_time()
        for stage in self.stages:
            if run_time < stage["duration"]:
                return stage["users"], stage["spawn_rate"]
        return None
