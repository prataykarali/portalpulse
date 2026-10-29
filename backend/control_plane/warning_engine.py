"""PortalPulse Module 8: Telemetry-Driven Warning Engine.

Connects telemetry conditions and control-cycle inferences to the 6 canonical warning experiences:
1. HIGH BOOKING DEMAND / RESULT-DAY RUSH
2. DATABASE CONNECTION POOL EXHAUSTION
3. VIRTUAL WAITING ROOM ACTIVE
4. HTTP 429 RATE LIMITING
5. GATEWAY TIMEOUT / REPLICA FAILOVER
6. CIRCUIT BREAKER TRIPPED

Requirements:
- Each warning has:
    * unique ID
    * severity (CRITICAL / WARNING)
    * trigger condition
    * timestamp
    * current metric
    * threshold
    * recommended action
    * current remediation state
    * recovery state
- Each warning display includes:
    * WHAT HAPPENED
    * WHY IT HAPPENED
    * WHAT PORTALPULSE DID
    * CURRENT RESULT
- Emitted as structured backend events via SSE.
- Real recovery event emitted when conditions normalize.
- Developer test trigger clearly marked with [TEST MODE].
"""

from __future__ import annotations

import logging
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("portalpulse.warning_engine")


@dataclass
class WarningItem:
    """Canonical warning definition for PortalPulse resilience alerting."""

    id: str
    title: str
    severity: str  # "CRITICAL" | "WARNING" | "RECOVERY"
    trigger_condition: str
    timestamp: str
    current_metric: str
    threshold: str
    recommended_action: str
    remediation_state: str
    recovery_state: str
    what_happened: str
    why_it_happened: str
    what_portalpulse_did: str
    current_result: str
    m4_rca: str = "DATABASE"
    m5_action: str = "ENABLE_WAITING_ROOM"
    m6_safety: str = "GUARDRAIL PASS"
    m7_actuating: str = "ACTUATING"
    is_test_mode: bool = False
    portal_id: str = "college_portal"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# Definition of the 6 canonical warnings
WARNING_SPECS: Dict[str, Dict[str, Any]] = {
    "WARN_RESULT_DAY_RUSH": {
        "title": "HIGH BOOKING DEMAND / RESULT-DAY RUSH",
        "severity": "WARNING",
        "trigger_condition": "virtual_users > 8000 or capacity_pressure > 75%",
        "threshold": "8,000 VUs / 75% Capacity",
        "recommended_action": "ENABLE_WAITING_ROOM",
        "remediation_state": "ADMISSION_THROTTLED",
        "recovery_state": "STABILIZED",
        "what_happened": "Massive surge in concurrent applicants attempting to access examination marksheets simultaneously.",
        "why_it_happened": "Synchronized result announcement exceeded baseline edge gateway ingress capacity.",
        "what_portalpulse_did": "M2 predicted safe-capacity breach in 7 min; M5 recommended dynamic waiting room tokens.",
        "current_result": "Ingress bounded; 12,481 concurrent users queued smoothly without 502/504 errors.",
        "m4_rca": "TRAFFIC_SPIKE",
        "m5_action": "ENABLE_WAITING_ROOM",
        "m6_safety": "GUARDRAIL PASS",
        "m7_actuating": "ACTUATING",
    },
    "WARN_DB_POOL_EXHAUSTION": {
        "title": "DATABASE CONNECTION POOL EXHAUSTION",
        "severity": "CRITICAL",
        "trigger_condition": "db_pool_utilization >= 90%",
        "threshold": "90% DB pool utilization",
        "recommended_action": "INCREASE_DB_POOL",
        "remediation_state": "ACTUATING",
        "recovery_state": "STABILIZED",
        "what_happened": "PostgreSQL connection pool reached 96% saturation (48 active conns out of 50 max).",
        "why_it_happened": "High concurrency transaction lock contention and slow aggregation queries during roll-number lookups.",
        "what_portalpulse_did": "M4 classified root cause as DATABASE (91.2%); M5 recommended INCREASE_DB_POOL; M6 passed blast radius guardrails; M7 scaled pool ceiling.",
        "current_result": "96% → 44% (pool utilization reduced to 22 / 50 conns).",
        "m4_rca": "DATABASE",
        "m5_action": "INCREASE_DB_POOL",
        "m6_safety": "GUARDRAIL PASS",
        "m7_actuating": "ACTUATING",
    },
    "WARN_WAITING_ROOM_ACTIVE": {
        "title": "VIRTUAL WAITING ROOM ACTIVE",
        "severity": "CRITICAL",
        "trigger_condition": "waiting_room_enabled == true",
        "threshold": "Waiting room enabled",
        "recommended_action": "ENABLE_WAITING_ROOM",
        "remediation_state": "ADMISSION_THROTTLED",
        "recovery_state": "DRAINING",
        "what_happened": "Autonomous Virtual Waiting Room actively throttling admissions to prevent complete backend collapse.",
        "why_it_happened": "Request arrival rate exceeded downstream database throughput limit of 450 RPS.",
        "what_portalpulse_did": "M5 deployed cryptographic token-bucket queue, metering users into the portal at safe capacity (450 RPS).",
        "current_result": "p95 latency normalized from 2.41s → 1.62s; zero backend dropouts.",
        "m4_rca": "DATABASE",
        "m5_action": "ENABLE_WAITING_ROOM",
        "m6_safety": "GUARDRAIL PASS",
        "m7_actuating": "ACTUATING",
    },
    "WARN_HTTP_429_RATE_LIMITING": {
        "title": "HTTP 429 RATE LIMITING",
        "severity": "WARNING",
        "trigger_condition": "observed HTTP 429 responses > 0",
        "threshold": "One HTTP 429 response",
        "recommended_action": "ACTIVATE_RATE_LIMIT",
        "remediation_state": "RATE_LIMITED",
        "recovery_state": "NORMAL",
        "what_happened": "Edge ingress dropping abusive refresh scripts with HTTP 429 Too Many Requests.",
        "why_it_happened": "Panicked student multi-tab polling and automated scrapers overwhelming public search endpoints.",
        "what_portalpulse_did": "M4 identified TRAFFIC_SPIKE; M5 engaged distributed sliding-window token rate limiting per IP.",
        "current_result": "Abusive traffic dropped with 0 ms origin overhead; legitimate human sessions protected.",
        "m4_rca": "TRAFFIC_SPIKE",
        "m5_action": "ACTIVATE_RATE_LIMIT",
        "m6_safety": "GUARDRAIL PASS",
        "m7_actuating": "ACTUATING",
    },
    "WARN_GATEWAY_TIMEOUT_FAILOVER": {
        "title": "GATEWAY TIMEOUT / REPLICA FAILOVER",
        "severity": "CRITICAL",
        "trigger_condition": "observed HTTP 504 or p99 > 3.0s",
        "threshold": "3.00s p99 latency",
        "recommended_action": "DIVERT_READS_TO_REPLICA",
        "remediation_state": "FAILOVER_ACTIVE",
        "recovery_state": "RECOVERED",
        "what_happened": "Gateway timeouts caused p99 latency to reach 3.85s with 279 HTTP 5xx responses.",
        "why_it_happened": "Primary database worker stall under concurrent marksheet PDF generation workloads.",
        "what_portalpulse_did": "M5 triggered DIVERT_READS_TO_REPLICA; M7 shifted 70% of read traffic to read-only PostgreSQL standby replicas.",
        "current_result": "3.85s → 1.10s; 5xx errors dropped from 279 → 0.",
        "m4_rca": "DATABASE",
        "m5_action": "DIVERT_READS_TO_REPLICA",
        "m6_safety": "GUARDRAIL PASS",
        "m7_actuating": "ACTUATING",
    },
    "WARN_CIRCUIT_BREAKER_TRIPPED": {
        "title": "CIRCUIT BREAKER TRIPPED",
        "severity": "CRITICAL",
        "trigger_condition": "circuit_breaker_enabled == true",
        "threshold": "Circuit breaker enabled",
        "recommended_action": "ENGAGE_CIRCUIT_BREAKER",
        "remediation_state": "CIRCUIT_OPEN",
        "recovery_state": "HALF_OPEN",
        "what_happened": "Circuit Breaker tripped to OPEN state on auxiliary report generation service.",
        "why_it_happened": "Error rate spiked to 5.8%, violating the 5.0% SLO error budget.",
        "what_portalpulse_did": "M5 opened circuit breaker to shed marksheet PDF rendering, shedding non-essential load to safeguard core login.",
        "current_result": "Critical system cascading failure averted; stepping to HALF_OPEN probe state.",
        "m4_rca": "DEPENDENCY_FAILURE",
        "m5_action": "ENGAGE_CIRCUIT_BREAKER",
        "m6_safety": "GUARDRAIL PASS",
        "m7_actuating": "ACTUATING",
    },
}


class WarningEngine:
    """Stateful Warning Engine that maps live telemetry and control cycles to the 6 warning experiences."""

    def __init__(self) -> None:
        self._active_warnings: Dict[str, WarningItem] = {}
        self._history: List[WarningItem] = []
        self._last_evaluated: float = 0.0

    def evaluate(self, cycle: Any) -> Tuple[List[WarningItem], List[Dict[str, Any]]]:
        """Evaluate a ControlCycle and return (new_warnings, recoveries)."""
        now_ts = datetime.now(timezone.utc).isoformat()
        new_warnings: List[WarningItem] = []
        recoveries: List[Dict[str, Any]] = []

        pre = cycle.pre_metrics or {}
        post = cycle.post_metrics or {}
        forecast = cycle.forecast or {}
        anomaly = cycle.anomaly or {}
        rca = cycle.rca or {}
        action_rec = cycle.action_recommendation or {}

        # Evaluate only observed simulator/control-plane state. IEMCRP reports DB
        # connections as utilization percent, while Nirantar may report counts.
        from backend.simulation.traffic_controller import TRAFFIC_CONTROLLER
        from backend.portals.iemcrp_app import IEMCRP_INFRA_STATE
        traffic = TRAFFIC_CONTROLLER.get_status()
        portal_id = getattr(cycle, "portal_id", "nirantar")
        recent = TRAFFIC_CONTROLLER.get_recent_transactions(200) if portal_id == "college_portal" and traffic.is_running else []
        hits_429 = sum(t.status == 429 for t in recent)
        hits_504 = sum(t.status == 504 for t in recent)
        hits_5xx = sum(t.status >= 500 for t in recent)
        vus = traffic.current_vus if portal_id == "college_portal" and traffic.is_running else 0
        db_raw = float(pre.get("db_connections", 0))
        db_pct = db_raw if portal_id == "college_portal" else db_raw * 2.0
        queue_len = int(pre.get("queue_length", 0))
        p99_ms = float(traffic.p99 if portal_id == "college_portal" else pre.get("p95_ms", 0) * 1.5)
        cap_pressure = float(forecast.get("capacity_pressure_index", 0))
        waiting_room = portal_id == "college_portal" and bool(IEMCRP_INFRA_STATE.get("waiting_room_enabled"))
        breaker = portal_id == "college_portal" and bool(IEMCRP_INFRA_STATE.get("circuit_breaker_enabled"))
        evaluations = {
            "WARN_RESULT_DAY_RUSH": (vus > 8000 or cap_pressure > 0.75, f"{vus:,} scenario VUs; capacity pressure {cap_pressure:.2f}"),
            "WARN_DB_POOL_EXHAUSTION": (db_pct >= 90, f"{db_pct:.1f}% DB pool utilization ({db_raw:g} reported)"),
            "WARN_WAITING_ROOM_ACTIVE": (waiting_room, f"waiting room enabled; {queue_len} queued"),
            "WARN_HTTP_429_RATE_LIMITING": (hits_429 > 0, f"{hits_429} observed HTTP 429 responses"),
            "WARN_GATEWAY_TIMEOUT_FAILOVER": (hits_504 > 0 or p99_ms > 3000, f"{hits_504} observed HTTP 504; p99 {p99_ms:.0f}ms"),
            "WARN_CIRCUIT_BREAKER_TRIPPED": (breaker, f"circuit breaker enabled; {hits_5xx} observed HTTP 5xx"),
        }

        for w_id, (is_active, metric_str) in evaluations.items():
            active_key = f"{portal_id}:{w_id}"
            spec = WARNING_SPECS[w_id]
            if is_active:
                if active_key not in self._active_warnings:
                    item = WarningItem(
                        id=w_id,
                        title=spec["title"],
                        severity=spec["severity"],
                        trigger_condition=spec["trigger_condition"],
                        timestamp=now_ts,
                        current_metric=metric_str,
                        threshold=spec["threshold"],
                        recommended_action=cycle.recommended_action,
                        remediation_state=cycle.actuation_status,
                        recovery_state=spec["recovery_state"],
                        what_happened=f"Observed {metric_str} during control cycle {getattr(cycle, "cycle_id", "unknown")}.",
                        why_it_happened=f"Model RCA: {rca.get('rca_class', 'unknown')} (confidence {rca.get('confidence', 0):.2f}).",
                        what_portalpulse_did=(
                            f"M5 selected {cycle.recommended_action}; M6 approved; M7 applied the action."
                            if cycle.actuation_status == "EXECUTED"
                            else f"M5 selected {cycle.recommended_action}; M6 held the change; M7 made no portal change."
                            if getattr(cycle, "safety_decision", "") == "REJECTED"
                            else f"M5 selected {cycle.recommended_action}; M6 found no action required; M7 continued monitoring."
                            if getattr(cycle, "safety_decision", "") == "NO_ACTION_REQUIRED"
                            else f"M5 selected {cycle.recommended_action}; M6 {getattr(cycle, 'safety_decision', 'unknown')}; M7 {cycle.actuation_status}."
                        ),
                        current_result=f"Recovery {cycle.recovery_state}; verification {getattr(cycle, "verification_status", "unknown")}.",
                        m4_rca=str(rca.get("rca_class", "UNKNOWN")),
                        m5_action=cycle.recommended_action,
                        m6_safety=str(getattr(cycle, "safety_decision", "UNKNOWN")),
                        m7_actuating=cycle.actuation_status,
                        portal_id=portal_id,
                    )
                    self._active_warnings[active_key] = item
                    self._history.append(item)
                    new_warnings.append(item)
            else:
                if active_key in self._active_warnings:
                    old_item = self._active_warnings.pop(active_key)
                    rec = {
                        "id": w_id,
                        "title": f"CONDITION CLEARED: {spec['title']}",
                        "severity": "RECOVERY",
                        "timestamp": now_ts,
                        "trigger_condition": spec["trigger_condition"],
                        "current_metric": metric_str,
                        "previous_metric": old_item.current_metric,
                        "threshold": spec["threshold"],
                        "recommended_action": cycle.recommended_action,
                        "remediation_state": "OBSERVED_CLEAR",
                        "recovery_state": "NORMAL",
                        "what_happened": f"Bottleneck cleared. {spec['title']} returned to nominal thresholds.",
                        "why_it_happened": "The observed trigger condition cleared in this control cycle.",
                        "what_portalpulse_did": (
                            f"M7 applied {cycle.recommended_action}; verification {cycle.verification_status}."
                            if cycle.actuation_status == "EXECUTED"
                            else "PortalPulse observed the condition returning below its threshold; no M7 action is attributed to this clearance."
                        ),
                        "current_result": f"Stabilized ({old_item.current_metric} → {metric_str})",
                        "is_recovered": True,
                    }
                    recoveries.append(rec)

        self._last_evaluated = time.time()
        return new_warnings, recoveries

    def trigger_test_scenario(self, warning_id: str) -> WarningItem:
        """Developer/demo trigger strictly flagged as [TEST MODE]."""
        if warning_id not in WARNING_SPECS:
            raise ValueError(f"Unknown warning ID: {warning_id}. Valid IDs: {list(WARNING_SPECS.keys())}")

        spec = WARNING_SPECS[warning_id]
        now_ts = datetime.now(timezone.utc).isoformat()
        item = WarningItem(
            id=warning_id,
            title=f"[TEST MODE] {spec['title']}",
            severity=spec["severity"],
            trigger_condition=spec["trigger_condition"],
            timestamp=now_ts,
            current_metric=f"TEST_METRIC_VALUE ({spec['threshold']})",
            threshold=spec["threshold"],
            recommended_action=spec["recommended_action"],
            remediation_state=spec["remediation_state"],
            recovery_state=spec["recovery_state"],
            what_happened=f"[TEST MODE] Injected simulated scenario for {spec['title']}.",
            why_it_happened=spec["why_it_happened"],
            what_portalpulse_did=spec["what_portalpulse_did"],
            current_result=spec["current_result"],
            m4_rca=spec["m4_rca"],
            m5_action=spec["m5_action"],
            m6_safety=spec["m6_safety"],
            m7_actuating=spec["m7_actuating"],
            is_test_mode=True,
        )
        self._active_warnings[warning_id] = item
        self._history.append(item)
        return item

    def get_active_warnings(self) -> List[Dict[str, Any]]:
        return [item.to_dict() for item in self._active_warnings.values()]

    def reset(self, portal_id: str | None = None) -> None:
        if portal_id is None:
            self._active_warnings.clear()
            self._history.clear()
            return
        self._active_warnings = {key: item for key, item in self._active_warnings.items() if item.portal_id != portal_id}
        self._history = [item for item in self._history if item.portal_id != portal_id]

    def get_catalog(self) -> Dict[str, Dict[str, Any]]:
        return WARNING_SPECS


# Global singleton instance
WARNING_ENGINE = WarningEngine()
