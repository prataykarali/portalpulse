"""PortalPulse Module 1: In-Memory Ring Buffer Collector & Persistence Engine.

Maintains rolling telemetry in a thread-safe circular buffer, computes real-time derived
lag/rolling features, evaluates SLA breaches, and logs to SQLite WAL storage.
"""

from __future__ import annotations

import collections
import sqlite3
import threading
from pathlib import Path

from backend.m1_monitoring.schema import (
    DerivedFeatures,
    HealthStatus,
    LiveTelemetryStatus,
    RawTelemetry,
    ScenarioConfig,
    ScenarioType,
)

ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT_DIR / "backend" / "data"
DB_PATH = DATA_DIR / "telemetry_history.db"

SLA_LATENCY_MS = 800.0
SLA_CPU_PERCENT = 85.0
SLA_ERROR_RATE = 0.01
SLA_DB_POOL_PERCENT = 90.0


class TelemetryCollector:
    """Thread-safe ring buffer and feature engineering engine for M1."""

    def __init__(self, max_buffer_size: int = 1800, db_path: Path | None = None) -> None:
        self.lock = threading.Lock()
        self.max_buffer_size = max_buffer_size
        self.buffer: collections.deque[RawTelemetry] = collections.deque(maxlen=max_buffer_size)
        self.current_scenario: ScenarioType = ScenarioType.NORMAL
        self.db_path = db_path or DB_PATH
        self._init_sqlite()

    def _init_sqlite(self) -> None:
        """Initialize SQLite WAL database table for historical persistence."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS telemetry_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    active_users INTEGER NOT NULL,
                    requests_per_sec REAL NOT NULL,
                    cpu_percent REAL NOT NULL,
                    ram_percent REAL NOT NULL,
                    network_in REAL NOT NULL,
                    network_out REAL NOT NULL,
                    response_time REAL NOT NULL,
                    throughput REAL NOT NULL,
                    error_rate REAL NOT NULL,
                    http_5xx REAL NOT NULL,
                    db_latency REAL NOT NULL,
                    db_connections REAL NOT NULL,
                    queue_length INTEGER NOT NULL,
                    service_instances INTEGER NOT NULL,
                    scenario TEXT NOT NULL
                );
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_telemetry_ts ON telemetry_records(timestamp);")
            conn.commit()

    def record_telemetry(
        self, raw: RawTelemetry, scenario: ScenarioType | None = None
    ) -> LiveTelemetryStatus:
        """Ingest a new raw telemetry observation and compute derived features."""
        with self.lock:
            if scenario:
                self.current_scenario = scenario

            self.buffer.append(raw)
            derived = self._compute_derived_features()
            live_status = self._evaluate_status(raw, derived)

            # Persist asynchronously / safely to SQLite
            self._persist_row(raw, self.current_scenario)

            return live_status

    # Backward-compatible ingestion alias
    ingest = record_telemetry

    def _persist_row(self, raw: RawTelemetry, scenario: ScenarioType) -> None:
        """Append a single record into SQLite database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    INSERT INTO telemetry_records (
                        timestamp, active_users, requests_per_sec, cpu_percent, ram_percent,
                        network_in, network_out, response_time, throughput, error_rate,
                        http_5xx, db_latency, db_connections, queue_length, service_instances, scenario
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        raw.timestamp,
                        raw.active_users,
                        raw.requests_per_sec,
                        raw.cpu_percent,
                        raw.ram_percent,
                        raw.network_in,
                        raw.network_out,
                        raw.response_time,
                        raw.throughput,
                        raw.error_rate,
                        raw.http_5xx,
                        raw.db_latency,
                        raw.db_connections,
                        raw.queue_length,
                        raw.service_instances,
                        scenario.value,
                    ),
                )
                conn.commit()
        except Exception:  # noqa: BLE001, S110
            pass  # Non-blocking logging failure tolerance

    def _compute_derived_features(self) -> DerivedFeatures:
        """Calculate the 9 derived lag, rolling, and velocity features."""
        buf = list(self.buffer)
        n = len(buf)
        curr = buf[-1]

        # 1-step and 5-step lags (defaults to current if buffer is young)
        idx_lag1 = max(0, n - 2)
        idx_lag5 = max(0, n - 6)

        cpu_lag_1 = buf[idx_lag1].cpu_percent
        cpu_lag_5 = buf[idx_lag5].cpu_percent
        rps_lag_1 = buf[idx_lag1].requests_per_sec
        rps_lag_5 = buf[idx_lag5].requests_per_sec

        # Rolling 5-step window
        window_5 = buf[max(0, n - 5) :]
        rolling_rps_5m = round(sum(r.requests_per_sec for r in window_5) / len(window_5), 2)
        rolling_latency_5m = round(sum(r.response_time for r in window_5) / len(window_5), 2)
        rolling_cpu_5m = round(sum(r.cpu_percent for r in window_5) / len(window_5), 2)

        # Traffic & Error Growth Rates
        traffic_growth_rate = round((curr.requests_per_sec - rps_lag_5) / max(rps_lag_5, 1.0), 4)
        error_growth_rate = round(
            (curr.error_rate - buf[idx_lag5].error_rate) / max(buf[idx_lag5].error_rate, 0.001),
            4,
        )

        return DerivedFeatures(
            cpu_lag_1=cpu_lag_1,
            cpu_lag_5=cpu_lag_5,
            rps_lag_1=rps_lag_1,
            rps_lag_5=rps_lag_5,
            rolling_rps_5m=rolling_rps_5m,
            rolling_latency_5m=rolling_latency_5m,
            rolling_cpu_5m=rolling_cpu_5m,
            traffic_growth_rate=traffic_growth_rate,
            error_growth_rate=error_growth_rate,
        )

    def _evaluate_status(self, raw: RawTelemetry, derived: DerivedFeatures) -> LiveTelemetryStatus:
        """Evaluate SLA thresholds, remaining capacity headroom, and health status."""
        sla_latency_breached = raw.response_time >= SLA_LATENCY_MS
        sla_cpu_breached = raw.cpu_percent >= SLA_CPU_PERCENT
        sla_error_breached = raw.error_rate >= SLA_ERROR_RATE
        sla_db_breached = raw.db_connections >= SLA_DB_POOL_PERCENT

        # Estimate safe capacity headroom (%)
        # Safe threshold is ~800 RPS per instance
        cluster_capacity = raw.service_instances * 780.0
        remaining_capacity_rps = cluster_capacity - raw.requests_per_sec
        headroom_percent = round((remaining_capacity_rps / max(cluster_capacity, 1.0)) * 100.0, 1)

        if (
            sla_latency_breached
            or sla_cpu_breached
            or sla_error_breached
            or sla_db_breached
            or headroom_percent < 5.0
        ):
            status = HealthStatus.CRITICAL
            msg = (
                f"SLA BREACH DETECTED: Latency {raw.response_time:.0f}ms (limit {SLA_LATENCY_MS:.0f}ms), "
                f"CPU {raw.cpu_percent:.1f}% (limit {SLA_CPU_PERCENT}%), "
                f"DB Pool {raw.db_connections:.1f}% (limit {SLA_DB_POOL_PERCENT}%)."
            )
        elif (
            raw.cpu_percent >= 70.0
            or raw.response_time >= 400.0
            or raw.db_connections >= 75.0
            or headroom_percent < 25.0
        ):
            status = HealthStatus.WARNING
            msg = f"Approaching saturation knee: Headroom at {headroom_percent:.1f}%. Scaling recommended."
        else:
            status = HealthStatus.NOMINAL
            msg = f"System healthy: Operating with {headroom_percent:.1f}% capacity headroom."

        return LiveTelemetryStatus(
            raw=raw,
            derived=derived,
            health_status=status,
            sla_latency_breached=sla_latency_breached,
            sla_cpu_breached=sla_cpu_breached,
            sla_error_breached=sla_error_breached,
            sla_db_breached=sla_db_breached,
            scenario=self.current_scenario,
            headroom_percent=headroom_percent,
            message=msg,
        )

    def get_latest_status(self) -> LiveTelemetryStatus | None:
        """Fetch the most recent telemetry state with derived features."""
        with self.lock:
            if not self.buffer:
                return None
            curr = self.buffer[-1]
            derived = self._compute_derived_features()
            return self._evaluate_status(curr, derived)

    def get_latest_telemetry(self) -> RawTelemetry | None:
        """Fetch the most recent raw telemetry record."""
        with self.lock:
            return self.buffer[-1] if self.buffer else None

    def compute_derived_features(self, raw: RawTelemetry | None = None) -> DerivedFeatures:
        """Compute rolling and lag features from the current telemetry buffer."""
        with self.lock:
            return self._compute_derived_features()

    def get_history(self, limit: int = 60) -> list[RawTelemetry]:
        """Return the most recent observations up to limit."""
        with self.lock:
            items = list(self.buffer)
            return items[-limit:] if items else []

    def set_scenario(self, cfg: ScenarioConfig) -> None:
        """Update active workload scenario configuration."""
        with self.lock:
            self.current_scenario = cfg.scenario_type

    def clear(self) -> None:
        """Clear memory buffer."""
        with self.lock:
            self.buffer.clear()


# Global Singleton Collector instance
COLLECTOR = TelemetryCollector()
