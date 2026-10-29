"""Bounded, continuous Nirantar bridge simulation for the public overlay.

Requests exercise the mounted local Nirantar ASGI application. They never hit
the separately deployed Nirantar website. Only an explicit stop (or process
shutdown / safety failure) ends a run.
"""

from __future__ import annotations

import asyncio
import math
import random
import time
from collections import deque
from pathlib import Path
from typing import Any

import httpx
from fastapi import APIRouter

from backend.connectors.nirantar_bridge import NIRANTAR_APP, NIRANTAR_INFRA_STATE, NIRANTAR_SESSION_TRACKER
from backend.streaming.broadcaster import STREAM_BROADCASTER

router = APIRouter(prefix="/api/v1/nirantar-simulation", tags=["nirantar-simulation"])


class NirantarSimulation:
    MAX_RPS = 10.0
    MAX_IN_FLIGHT = 4
    PHASES = (
        ("Steady journeys", 2.2, "NONE", 0),
        ("Tatkal arrival", 8.5, "NONE", 0),
        ("Booking contention", 6.8, "NONE", 190),
        ("Gateway fault", 5.5, "GATEWAY", 0),
        ("Mitigation window", 4.2, "NONE", 75),
        ("Recovery check", 2.8, "NONE", 0),
        ("Second wave", 9.2, "NONE", 105),
    )

    def __init__(self) -> None:
        self._initial_infra = dict(NIRANTAR_INFRA_STATE)
        self.task: asyncio.Task | None = None
        self.pending: set[asyncio.Task] = set()
        self.running = False
        self.started_at = 0.0
        self.phase = "Idle"
        self.phase_index = 0
        self.stop_reason = "Not started"
        self.total_requests = 0
        self.total_failures = 0
        self.recent: deque[tuple[float, int, float]] = deque(maxlen=250)
        self.latest: dict[str, Any] = {}

    def snapshot(self) -> dict[str, Any]:
        now = time.monotonic()
        while self.recent and self.recent[0][0] < now - 8:
            self.recent.popleft()
        window = [entry for entry in self.recent if entry[0] >= now - 3]
        recent_latencies = sorted(latency for _, _, latency in window)
        p95 = recent_latencies[min(len(recent_latencies) - 1, int(len(recent_latencies) * 0.95))] if recent_latencies else 0.0
        ux = NIRANTAR_SESSION_TRACKER.get_ux_metrics()
        return {
            "running": self.running,
            "portal_id": "nirantar",
            "scenario": "NIRANTAR_LIVE_SIMULATION",
            "phase": self.phase,
            "elapsed_seconds": round(now - self.started_at, 1) if self.running else 0,
            "rps": round(len(window) / 3, 2),
            "p95_ms": round(p95, 1),
            "error_rate": round(100 * sum(status >= 400 for _, status, _ in window) / len(window), 1) if window else 0.0,
            "http_5xx_pct": ux.get("ux_5xx_rate", 0.0),
            "http_429_pct": ux.get("ux_429_rate", 0.0),
            "in_flight": len(self.pending),
            "queue": NIRANTAR_SESSION_TRACKER.waiting_room.get_status().get("queue_length", 0),
            "total_requests": self.total_requests,
            "total_failures": self.total_failures,
            "stop_reason": self.stop_reason,
            "max_rps": self.MAX_RPS,
            "max_in_flight": self.MAX_IN_FLIGHT,
            "simulated_fault": NIRANTAR_INFRA_STATE["sim_fault"],
        }

    async def start(self) -> dict[str, Any]:
        if self.running:
            return self.snapshot()
        self.running = True
        self.started_at = time.monotonic()
        self.stop_reason = "Running until manually stopped"
        self.phase_index = 0
        self.total_requests = self.total_failures = 0
        self.recent.clear()
        NIRANTAR_INFRA_STATE.update(self._initial_infra)
        NIRANTAR_SESSION_TRACKER.waiting_room.disable()
        NIRANTAR_SESSION_TRACKER.rate_limiter.set_rate_limit(None)
        self.task = asyncio.create_task(self._run())
        return self.snapshot()

    async def stop(self) -> dict[str, Any]:
        if self.task and not self.task.done():
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        self.running = False
        self.stop_reason = "Stopped by operator"
        NIRANTAR_INFRA_STATE["sim_fault"] = "NONE"
        NIRANTAR_INFRA_STATE["sim_latency_ms"] = 0
        NIRANTAR_INFRA_STATE.update(self._initial_infra)
        NIRANTAR_SESSION_TRACKER.waiting_room.disable()
        NIRANTAR_SESSION_TRACKER.rate_limiter.set_rate_limit(None)
        result = self.snapshot()
        STREAM_BROADCASTER.publish("nirantar_simulation", result)
        return result

    async def _request(self, client: httpx.AsyncClient) -> None:
        started = time.monotonic()
        try:
            path = "/booking/tatkal" if random.random() < 0.32 else "/trains/search"
            if path == "/booking/tatkal":
                response = await client.post(path, json={"train_number": "12001", "passenger_name": "Simulation Passenger"})
            else:
                response = await client.get(path, params={"source": random.choice(["NDLS", "MMCT", "HWH", "SBC"])})
            status = response.status_code
        except Exception:
            status = 599
        self.total_requests += 1
        self.total_failures += int(status >= 400)
        self.recent.append((time.monotonic(), status, (time.monotonic() - started) * 1000))

    async def _run(self) -> None:
        phase_end = 0.0
        next_request = time.monotonic()
        next_publish = 0.0
        next_thermal_check = 0.0
        try:
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=NIRANTAR_APP), base_url="http://nirantar.local", timeout=3.0) as client:
                while self.running:
                    now = time.monotonic()
                    if now >= next_thermal_check:
                        next_thermal_check = now + 5
                        try:
                            temperatures = [int(path.read_text().strip()) for path in Path('/sys/class/thermal').glob('thermal_zone*/temp')]
                            if any(temp >= 85000 for temp in temperatures):
                                self.stop_reason = 'Thermal safety stop (85°C)'
                                break
                        except (OSError, ValueError):
                            pass
                    if now >= phase_end:
                        self.phase_index = (self.phase_index + 1) % len(self.PHASES) if phase_end else 0
                        label, _, fault, delay = self.PHASES[self.phase_index]
                        self.phase = label
                        NIRANTAR_INFRA_STATE["sim_fault"] = fault
                        NIRANTAR_INFRA_STATE["sim_latency_ms"] = delay
                        phase_end = now + random.uniform(7, 12)
                    _, target, _, _ = self.PHASES[self.phase_index]
                    # A changing target produces visible bursts and lulls while
                    # never exceeding the server-side rate/concurrency ceiling.
                    wave = 0.68 + 0.32 * (1 + math.sin(now * 2.4))
                    target = max(0.8, min(self.MAX_RPS, target * wave * random.uniform(0.65, 1.25)))
                    if now >= next_request and len(self.pending) < self.MAX_IN_FLIGHT:
                        work = asyncio.create_task(self._request(client))
                        self.pending.add(work)
                        work.add_done_callback(self.pending.discard)
                        next_request = now + max(1 / self.MAX_RPS, 1 / target)
                    if now >= next_publish:
                        self.latest = self.snapshot()
                        STREAM_BROADCASTER.publish("nirantar_simulation", self.latest)
                        next_publish = now + 1
                    await asyncio.sleep(0.05)
        except asyncio.CancelledError:
            pass
        finally:
            self.running = False
            if self.stop_reason == 'Running until manually stopped':
                self.stop_reason = 'Simulation worker stopped'
            NIRANTAR_INFRA_STATE["sim_fault"] = "NONE"
            NIRANTAR_INFRA_STATE["sim_latency_ms"] = 0
            for work in tuple(self.pending):
                work.cancel()
            if self.pending:
                await asyncio.gather(*self.pending, return_exceptions=True)
            self.pending.clear()


NIRANTAR_SIMULATION = NirantarSimulation()


@router.get("/status")
def status() -> dict[str, Any]:
    return NIRANTAR_SIMULATION.snapshot()


@router.post("/start")
async def start() -> dict[str, Any]:
    return await NIRANTAR_SIMULATION.start()


@router.post("/stop")
async def stop() -> dict[str, Any]:
    return await NIRANTAR_SIMULATION.stop()
