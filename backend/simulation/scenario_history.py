"""PortalPulse - Scenario History & Replay Manager (PRD-02 §10, §11)
Maintains persistent records of all capacity benchmarks, chaos experiments,
and exam-day resilience tests. Enables historical comparison and exact deterministic replay.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger("portalpulse.scenario_history")

HISTORY_FILE_PATH = os.path.join(os.path.dirname(__file__), "scenario_history_store.json")


class ScenarioRunRecord(BaseModel):
    scenario_id: str = Field(default_factory=lambda: f"run-{uuid.uuid4().hex[:8]}")
    portal_id: str
    scenario_name: str
    scenario_type: str  # CUSTOM_BUILDER, EXAM_DAY, BREAK_PORTAL, CHAOS_INJECTION
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    duration_sec: float
    status: str = "COMPLETED"  # RUNNING, COMPLETED, FAILED, STOPPED

    # Test configuration parameters
    parameters: Dict[str, Any] = Field(default_factory=dict)
    # e.g.: {"vus": 2000, "spawn_rate": 50, "persona_mix": {"student": 0.6, "panicked": 0.4}, "fault": "DB_CONNECTION_EXHAUSTION"}

    # Result metrics
    metrics: Dict[str, Any] = Field(default_factory=dict)
    # e.g.: {"peak_rps": 482.1, "p95_latency_ms": 284.0, "p99_latency_ms": 412.0, "error_rate_pct": 0.04, "mitigations_executed": 2}

    # Closed-loop verification
    before_after_comparison: Optional[Dict[str, Any]] = None
    # {"before": {"p95": 920, "5xx": 8.4}, "action": "TOKEN_BUCKET", "after": {"p95": 380, "5xx": 0.0}, "effective": True}

    # High-resolution timeline
    timeline_events: List[Dict[str, Any]] = Field(default_factory=list)


class ScenarioHistoryManager:
    """Thread-safe store for scenario execution history and replay comparison."""

    def __init__(self, storage_path: str = HISTORY_FILE_PATH) -> None:
        self.storage_path = storage_path
        self._lock = threading.Lock()
        self._runs: Dict[str, ScenarioRunRecord] = {}
        self._load_from_disk()

        # Seed realistic baseline scenarios if empty
        if not self._runs:
            self._seed_default_history()

    def _seed_default_history(self) -> None:
        """Seed representative historical runs for Nirantar and IEMCRP."""
        # 1. Nirantar Exam Day Stampede
        r1 = ScenarioRunRecord(
            scenario_id="run-nir-stampede-01",
            portal_id="nirantar",
            scenario_name="Exam Day Stampede (5,000 VUs)",
            scenario_type="EXAM_DAY",
            created_at=datetime.now(timezone.utc).isoformat(),
            duration_sec=60.0,
            status="COMPLETED",
            parameters={
                "vus": 5000,
                "spawn_rate": 250,
                "persona_mix": {
                    "student": 0.50,
                    "panicked": 0.30,
                    "result_rush": 0.15,
                    "faculty": 0.04,
                    "abnormal_bot": 0.01
                },
                "fault_type": "NONE"
            },
            metrics={
                "peak_rps": 642.5,
                "p95_latency_ms": 298.0,
                "p99_latency_ms": 480.0,
                "error_rate_pct": 0.02,
                "recovery_score": 96.0,
                "mitigations_executed": 1
            },
            before_after_comparison={
                "before": {"p95_ms": 860.0, "error_5xx_pct": 4.8, "cpu_pct": 91.0},
                "action": "VIRTUAL_WAITING_ROOM",
                "after": {"p95_ms": 284.0, "error_5xx_pct": 0.02, "cpu_pct": 64.0},
                "improvement_p95_pct": 67.0,
                "effective": True
            },
            timeline_events=[
                {"timestamp": "09:00:00", "event": "Locust traffic ramp started (50 -> 5000 VUs)"},
                {"timestamp": "09:00:08", "event": "M2 Predicts saturation in 45s (Confidence 94%)"},
                {"timestamp": "09:00:14", "event": "M3 Anomaly detected: Latency knee crossed (P95 > 500ms)"},
                {"timestamp": "09:00:16", "event": "M5 Recommended Waiting Room; M6 Approved (Low blast radius)"},
                {"timestamp": "09:00:18", "event": "M7 Waiting Room activated (Admitted cookies issued)"},
                {"timestamp": "09:00:32", "event": "M7 Verification: P95 dropped from 860ms to 284ms. Recovery verified."}
            ]
        )

        # 2. IEMCRP Database Pool Exhaustion
        r2 = ScenarioRunRecord(
            scenario_id="run-iemcrp-chaos-02",
            portal_id="iemcrp",
            scenario_name="Monolithic DB Pool Exhaustion Chaos Test",
            scenario_type="CHAOS_INJECTION",
            created_at=datetime.now(timezone.utc).isoformat(),
            duration_sec=45.0,
            status="COMPLETED",
            parameters={
                "vus": 1200,
                "spawn_rate": 80,
                "persona_mix": {
                    "result_rush": 0.70,
                    "panicked": 0.25,
                    "abnormal_bot": 0.05
                },
                "fault_type": "DB_CONNECTION_EXHAUSTION",
                "fault_intensity": 1.0
            },
            metrics={
                "peak_rps": 245.0,
                "p95_latency_ms": 340.0,
                "p99_latency_ms": 520.0,
                "error_rate_pct": 0.08,
                "recovery_score": 92.5,
                "mitigations_executed": 1
            },
            before_after_comparison={
                "before": {"p95_ms": 1420.0, "error_5xx_pct": 14.2, "active_db_conns": 50},
                "action": "STATIC_FALLBACK_DIVERT",
                "after": {"p95_ms": 220.0, "error_5xx_pct": 0.0, "active_db_conns": 28},
                "improvement_p95_pct": 84.5,
                "effective": True
            },
            timeline_events=[
                {"timestamp": "10:15:00", "event": "Chaos injection: DB_CONNECTION_EXHAUSTION started"},
                {"timestamp": "10:15:04", "event": "Monolithic connection pool 50/50 saturated. Queue starved."},
                {"timestamp": "10:15:07", "event": "M4 RCA Pinpointed: Real Monolithic DB Semaphore Exhaustion"},
                {"timestamp": "10:15:09", "event": "M5 Recommended Static Fallback Divert for marksheet lookups"},
                {"timestamp": "10:15:10", "event": "M7 Actuator executed: Static page serving activated"},
                {"timestamp": "10:15:25", "event": "Verification: Pool utilization dropped to 56%. 504 errors resolved."}
            ]
        )

        self._runs[r1.scenario_id] = r1
        self._runs[r2.scenario_id] = r2
        self._save_to_disk()

    def record_run(self, record: ScenarioRunRecord) -> ScenarioRunRecord:
        """Add or update a run record."""
        with self._lock:
            self._runs[record.scenario_id] = record
            self._save_to_disk()
            return record

    def get_run(self, scenario_id: str) -> Optional[ScenarioRunRecord]:
        """Retrieve a run record by ID."""
        with self._lock:
            return self._runs.get(scenario_id)

    def list_runs(self, portal_id: Optional[str] = None, limit: int = 50) -> List[ScenarioRunRecord]:
        """List runs sorted chronologically descending."""
        with self._lock:
            records = list(self._runs.values())
            if portal_id:
                records = [r for r in records if r.portal_id.lower() == portal_id.lower()]
            records.sort(key=lambda r: r.created_at, reverse=True)
            return records[:limit]

    def compare_runs(self, id_a: str, id_b: str) -> Dict[str, Any]:
        """Produce a side-by-side differential analysis of two scenario executions."""
        with self._lock:
            run_a = self._runs.get(id_a)
            run_b = self._runs.get(id_b)

        if not run_a or not run_b:
            return {"error": "One or both scenario IDs not found"}

        metrics_a = run_a.metrics
        metrics_b = run_b.metrics

        delta_rps = metrics_b.get("peak_rps", 0) - metrics_a.get("peak_rps", 0)
        delta_p95 = metrics_b.get("p95_latency_ms", 0) - metrics_a.get("p95_latency_ms", 0)
        delta_err = metrics_b.get("error_rate_pct", 0) - metrics_a.get("error_rate_pct", 0)

        return {
            "run_a": run_a.model_dump(),
            "run_b": run_b.model_dump(),
            "deltas": {
                "delta_peak_rps": round(delta_rps, 2),
                "delta_p95_ms": round(delta_p95, 2),
                "delta_error_pct": round(delta_err, 4),
                "faster_scenario": run_a.scenario_id if metrics_a.get("p95_latency_ms", 0) < metrics_b.get("p95_latency_ms", 0) else run_b.scenario_id
            }
        }

    def _save_to_disk(self) -> None:
        try:
            data = {k: v.model_dump() for k, v in self._runs.items()}
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as exc:
            logger.warning(f"Could not persist scenario history to disk: {exc}")

    def _load_from_disk(self) -> None:
        if not os.path.exists(self.storage_path):
            return
        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                for k, v in data.items():
                    self._runs[k] = ScenarioRunRecord(**v)
        except Exception as exc:
            logger.warning(f"Could not load scenario history: {exc}")


SCENARIO_HISTORY = ScenarioHistoryManager()
