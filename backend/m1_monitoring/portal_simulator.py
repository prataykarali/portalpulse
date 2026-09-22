"""PortalPulse Module 1: High-Concurrency Portal Simulator.

Simulates synthetic high-load portal dynamics (e.g., IRCTC / University ERP),
generating realistic 15-signal telemetry with queueing physics, knee transitions,
and scenario-specific fault patterns.
"""

from __future__ import annotations

import math
import random
from datetime import datetime, timezone

from backend.m1_monitoring.schema import RawTelemetry, ScenarioConfig, ScenarioType


class PortalSimulator:
    """Simulates a multi-tier web application (Client -> API Gateway -> Backend Pods -> Database/Cache)."""

    def __init__(self, config: ScenarioConfig | None = None) -> None:
        self.config = config or ScenarioConfig(scenario_type=ScenarioType.NORMAL)
        self.tick: int = 0
        self.baseline_users: int = 24000
        self.current_users: float = 24000.0
        self.service_instances: int = 4

    def update_config(self, config: ScenarioConfig) -> None:
        """Update simulation runtime configuration."""
        self.config = config
        self.service_instances = config.service_instances

    def generate_step(self, step_time: datetime | None = None) -> RawTelemetry:
        """Generate one step of realistic telemetry based on current scenario and queueing dynamics."""
        self.tick += 1
        ts = step_time or datetime.now(timezone.utc)
        iso_ts = ts.isoformat()
        sc = self.config.scenario_type
        mult = self.config.user_multiplier
        pods = max(1, self.service_instances)

        # Baseline Diurnal User Drift
        diurnal = 1.0 + 0.25 * math.sin(self.tick * 0.05)
        noise = random.uniform(-0.03, 0.03)

        if sc == ScenarioType.NORMAL:
            target_users = 22000 * mult * diurnal
            self.current_users += (target_users - self.current_users) * 0.15 + (noise * 500)
            workload_factor = 1.0
            db_weight = 1.0
            cpu_weight = 1.0

        elif sc == ScenarioType.RESULT_RUSH:
            # Sudden massive influx of students checking grades
            target_users = 85000 * mult * diurnal
            self.current_users += (target_users - self.current_users) * 0.25 + (noise * 1200)
            workload_factor = 1.6
            db_weight = 2.4
            cpu_weight = 1.3

        elif sc == ScenarioType.FEE_REGISTRATION:
            # High concurrency with transactional payment lock contention
            target_users = 55000 * mult * diurnal
            self.current_users += (target_users - self.current_users) * 0.20 + (noise * 800)
            workload_factor = 1.35
            db_weight = 1.9
            cpu_weight = 1.2

        elif sc == ScenarioType.FLASH_CROWD:
            # Explosive viral link surge hitting API gateway
            target_users = 110000 * mult
            self.current_users += (target_users - self.current_users) * 0.35 + (noise * 2000)
            workload_factor = 1.8
            db_weight = 1.2
            cpu_weight = 1.6

        elif sc == ScenarioType.DATABASE_LOCK_JAM:
            # Moderate users, but database deadlock/query starvation
            target_users = 35000 * mult
            self.current_users += (target_users - self.current_users) * 0.15 + (noise * 400)
            workload_factor = 1.2
            db_weight = 4.5
            cpu_weight = 0.9

        elif sc == ScenarioType.WORKER_CPU_SATURATION:
            # Heavy computational queries pegging workers
            target_users = 40000 * mult
            self.current_users += (target_users - self.current_users) * 0.15 + (noise * 400)
            workload_factor = 1.4
            db_weight = 1.1
            cpu_weight = 3.5

        elif sc == ScenarioType.NETWORK_THROTTLING:
            # Ingress socket queue congestion
            target_users = 32000 * mult
            self.current_users += (target_users - self.current_users) * 0.15 + (noise * 400)
            workload_factor = 1.1
            db_weight = 1.0
            cpu_weight = 1.0
        else:
            target_users = 22000
            self.current_users = target_users
            workload_factor = 1.0
            db_weight = 1.0
            cpu_weight = 1.0

        active_users = max(100, int(self.current_users))

        # Request arrival rate (RPS): ~ 0.05 to 0.08 requests per active user per second
        arrival_rps = round(active_users * (0.058 * workload_factor) + random.uniform(-25, 25), 1)
        arrival_rps = max(5.0, arrival_rps)

        # Capacity saturation knee per pod (~800 RPS per pod at nominal load)
        cluster_capacity_rps = pods * 780.0
        utilization = arrival_rps / max(cluster_capacity_rps, 10.0)

        # CPU Utilization (%)
        base_cpu = 15.0
        cpu_dynamic = (utilization**1.35) * 65.0 * cpu_weight
        cpu_percent = round(min(99.5, max(12.0, base_cpu + cpu_dynamic + random.uniform(-2.0, 2.0))), 1)

        # RAM Utilization (%)
        base_ram = 38.0
        ram_dynamic = (utilization**0.8) * 40.0 + (pods * 2.0)
        ram_percent = round(min(96.0, max(25.0, base_ram + ram_dynamic + random.uniform(-1.0, 1.0))), 1)

        # Database Connection Pool Utilization (%)
        # Baseline pool has 100 connections
        db_pool_capacity = 100.0 + (pods * 15.0)
        db_demand = (arrival_rps * 0.045) * db_weight
        db_connections = round(
            min(
                98.5,
                max(
                    15.0,
                    (db_demand / db_pool_capacity) * 100.0 + random.uniform(-3.0, 3.0),
                ),
            ),
            1,
        )

        # Database Query Latency (ms)
        # Follows hyperbolic surge as DB pool nears 100% saturation
        base_db_lat = 28.0 + self.config.inject_db_delay_ms
        if db_connections > 75.0:
            db_lat_multiplier = 1.0 + 9.0 * ((db_connections - 75.0) / 25.0) ** 2.2
        else:
            db_lat_multiplier = 1.0 + 0.3 * (db_connections / 75.0)
        db_latency = round(
            min(
                4500.0,
                max(15.0, base_db_lat * db_lat_multiplier + random.uniform(-5.0, 15.0)),
            ),
            1,
        )

        # Application Round-Trip Latency (ms)
        # Includes gateway, app compute, queueing, and database wait time
        base_app_lat = 45.0 + (db_latency * 0.75)
        if utilization > 0.80:
            queueing_surge = 1200.0 * ((utilization - 0.80) / 0.20) ** 2.5
        else:
            queueing_surge = 0.0
        response_time = round(
            min(
                8000.0,
                max(35.0, base_app_lat + queueing_surge + random.uniform(-10.0, 20.0)),
            ),
            1,
        )

        # Ingress Queue / Waiting Room Backlog
        if utilization > 0.92:
            queue_length = int((utilization - 0.92) * arrival_rps * 1.5 + random.randint(50, 250))
        else:
            queue_length = max(0, int(random.randint(0, 15)))

        # Throughput and Error Rates
        if utilization > 1.05 or response_time > 1500.0 or db_connections > 92.0:
            # Overloaded: requests begin timing out or returning HTTP 503 / 504
            drop_fraction = min(0.45, max(0.02, (utilization - 1.0) * 0.35 + (response_time / 10000.0)))
            throughput = round(arrival_rps * (1.0 - drop_fraction), 1)
            error_rate = round(min(0.35, max(0.015, drop_fraction + random.uniform(-0.005, 0.015))), 4)
            http_5xx = round(arrival_rps * error_rate, 1)
        else:
            throughput = arrival_rps
            error_rate = round(max(0.0005, random.uniform(0.001, 0.004)), 4)
            http_5xx = round(arrival_rps * error_rate, 1)

        # Network Throughput (MB/s)
        network_in = round(arrival_rps * 0.075 + random.uniform(0.5, 2.0), 1)
        network_out = round(throughput * 0.185 + random.uniform(1.0, 4.0), 1)

        return RawTelemetry(
            timestamp=iso_ts,
            active_users=active_users,
            requests_per_sec=arrival_rps,
            cpu_percent=cpu_percent,
            ram_percent=ram_percent,
            network_in=network_in,
            network_out=network_out,
            response_time=response_time,
            throughput=throughput,
            error_rate=error_rate,
            http_5xx=http_5xx,
            db_latency=db_latency,
            db_connections=db_connections,
            queue_length=queue_length,
            service_instances=pods,
        )


# Global singleton simulator instance
SIMULATOR = PortalSimulator()

