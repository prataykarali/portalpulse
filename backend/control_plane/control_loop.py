"""PortalPulse Continuous Autonomous Control-Cycle Scheduler.

Fulfills PRD-03 & Continuous Control Architecture:
- Lifespan-managed background control loop inside FastAPI.
- Autonomous 3-second cycle cadence (2-4 seconds).
- Authoritative execution path:
  READ TELEMETRY -> RUN MODELS (M2, M3, M4, M5) -> DECIDE ->
  SAFETY VALIDATION (M6) -> ACTUATE (M7 if required/approved) ->
  INGEST RESULT TELEMETRY -> STORE ControlCycle.
- Robust exception handling so model exceptions do not kill the daemon.
- Anti-flapping and deterministic cooldown enforcement.
- Status, Latest, and History API endpoints.
"""

from __future__ import annotations

import asyncio
import os
import collections
import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from backend.control_plane.explainable_pipeline import EXPLAINABLE_PIPELINE, ControlCycle
from backend.control_plane.warning_engine import WARNING_ENGINE

logger = logging.getLogger("portalpulse.control_loop")


class ControlLoopStatus(BaseModel):
    """Status payload for GET /api/v1/control-loop/status."""

    running: bool
    cycle_id: Optional[str] = None
    interval_ms: int = 3000
    last_cycle: Optional[str] = None
    next_cycle: Optional[str] = None
    phase: str = "IDLE"
    current_action: str = "NO_OP"
    recovery_state: str = "NOMINAL"
    last_error: Optional[str] = None


class ContinuousControlLoop:
    """Autonomous background scheduler executing the closed-loop control cycle every ~3 seconds."""

    def __init__(self, interval_seconds: float = 3.0) -> None:
        self.interval_seconds = interval_seconds
        self.interval_ms = int(interval_seconds * 1000)
        self.running: bool = False
        self._task: Optional[asyncio.Task] = None
        self.cycle_id: Optional[str] = None
        self.last_cycle: Optional[str] = None
        self.next_cycle: Optional[str] = None
        self.phase: str = "IDLE"
        self.current_action: str = "NO_OP"
        self.recovery_state: str = "NOMINAL"
        self.last_error: Optional[str] = None
        self.history: collections.deque[ControlCycle] = collections.deque(maxlen=100)

    async def start(self) -> None:
        """Start the background control loop."""
        if self.running and self._task and not self._task.done():
            return
        self.running = True
        try:
            self._task = asyncio.create_task(self._run_loop())
            logger.info("[CONTROL_LOOP] Continuous autonomous control loop started.")
        except RuntimeError as exc:
            logger.warning(f"[CONTROL_LOOP] Could not create background task (no running loop): {exc}")

    async def stop(self) -> None:
        """Stop the background control loop cleanly."""
        self.running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
        self.phase = "STOPPED"
        logger.info("[CONTROL_LOOP] Continuous autonomous control loop stopped cleanly.")

    async def _run_loop(self) -> None:
        """Continuous execution loop running every ~3 seconds."""
        # Initial brief pause to let server startup settle
        try:
            await asyncio.sleep(0.5)
        except asyncio.CancelledError:
            return

        while self.running:
            if os.getenv("PORTALPULSE_DEMO_MODE") == "1":
                from backend.simulation.traffic_controller import TRAFFIC_CONTROLLER
                if not TRAFFIC_CONTROLLER.is_running or TRAFFIC_CONTROLLER.is_paused:
                    self.phase = "IDLE"
                    self.next_cycle = None
                    await asyncio.sleep(1.0)
                    continue
            now_dt = datetime.now(timezone.utc)
            self.next_cycle = (now_dt + timedelta(seconds=self.interval_seconds)).isoformat()
            try:
                self.step(
                    portal_id="college_portal" if os.getenv("PORTALPULSE_DEMO_MODE") == "1" else "nirantar",
                    auto_approve=os.getenv("PORTALPULSE_DEMO_MODE") == "1",
                )
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.last_error = str(e)
                self.phase = "ERROR_RECOVERING"
                logger.error(f"[CONTROL_LOOP] Error during autonomous control cycle: {e}", exc_info=True)
            finally:
                if self.running:
                    self.phase = "SLEEPING"

            try:
                await asyncio.sleep(self.interval_seconds)
            except asyncio.CancelledError:
                break

    def step(
        self,
        portal_id: str = "nirantar",
        auto_approve: bool = False,
        force_bypass_cooldown: bool = False,
    ) -> ControlCycle:
        """Execute one complete cycle of the real M1-M7 pipeline."""
        self.phase = "READ_TELEMETRY"
        try:
            self.phase = "RUN_MODELS"
            cycle = EXPLAINABLE_PIPELINE.run_cycle(
                portal_id=portal_id,
                auto_approve=auto_approve,
                force_bypass_cooldown=force_bypass_cooldown,
            )
            self._verify_pending_actions(cycle)

            self.phase = "RECORD_RESULT"
            self.cycle_id = cycle.cycle_id
            self.last_cycle = cycle.timestamp
            self.current_action = cycle.recommended_action
            self.recovery_state = cycle.recovery_state
            self.last_error = None

            self.history.append(cycle)
            self._broadcast_cycle(cycle)
            return cycle
        except Exception as e:
            self.last_error = str(e)
            self.phase = "ERROR_RECOVERING"
            logger.error(f"[CONTROL_LOOP] Cycle execution failed: {e}", exc_info=True)
            raise

    def _verify_pending_actions(self, current: ControlCycle) -> None:
        """Check an executed action against the next real M1 request windows."""
        from backend.streaming.broadcaster import STREAM_BROADCASTER

        for age, prior in enumerate(reversed(self.history), start=1):
            if age > 2:
                break
            if prior.portal_id != current.portal_id or prior.verification_status != "OBSERVING":
                continue
            before, after = prior.pre_metrics or {}, current.pre_metrics or {}
            error_before, error_after = float(before.get("errors", 0)), float(after.get("errors", 0))
            db_before, db_after = float(before.get("db_connections", 0)), float(after.get("db_connections", 0))
            p95_before, p95_after = float(before.get("p95_ms", 0)), float(after.get("p95_ms", 0))
            nonworse_errors = error_after <= error_before + 0.02
            improved = (
                error_before >= 0.05 and error_after <= error_before - 0.05
                or db_before >= 20 and db_after <= db_before - 5 and nonworse_errors
                or p95_before >= 30 and p95_after <= p95_before * 0.85 and nonworse_errors
            )
            if not improved and age < 2:
                continue
            prior.post_metrics = dict(after)
            prior.after_metrics = dict(after)
            prior.verification_status = "RECOVERY_VERIFIED" if improved else "RECOVERY_FAILED"
            prior.recovery_state = "STABILIZING" if improved else "DEGRADED"
            verify_record = prior.models.get("VERIFY")
            if verify_record:
                verify_record.output_summary["status"] = prior.verification_status
                verify_record.output_summary["follow_up_cycle"] = current.cycle_id
            if improved:
                STREAM_BROADCASTER.publish_recovery({
                    "type": "recovery",
                    "id": f"REC_STABILIZED_{prior.cycle_id}",
                    "title": "M7 POST-ACTION CHECK PASSED",
                    "portal_id": prior.portal_id,
                    "timestamp": current.timestamp,
                    "is_recovered": True,
                    "verification_status": "RECOVERY_VERIFIED",
                    "action": prior.recommended_action,
                    "pre_p95_ms": p95_before,
                    "post_p95_ms": p95_after,
                    "current_result": f"p95 {p95_before:.1f} → {p95_after:.1f} ms; errors {error_before*100:.1f} → {error_after*100:.1f}%",
                    "what_happened": "The next measured request window improved after the executed action.",
                    "what_portalpulse_did": f"M7 applied {prior.recommended_action}; M1 verified a later cycle.",
                    "message": "Measured request outcomes improved in the next control cycle; monitoring continues.",
                    "cycle_id": prior.cycle_id,
                    "follow_up_cycle": current.cycle_id,
                })

    def _broadcast_cycle(self, cycle: ControlCycle) -> None:
        """Broadcast real-time control plane events via SSE."""
        try:
            from backend.streaming.broadcaster import STREAM_BROADCASTER

            try:
                cycle_num = int(cycle.cycle_id.split("-")[-1])
            except Exception:
                cycle_num = 1

            phase = (
                "ACTUATING"
                if cycle.actuation_status == "EXECUTED"
                else ("ANALYZING" if cycle.human_approval_required else "MONITORING")
            )

            # 1. control_cycle
            STREAM_BROADCASTER.publish_control_cycle({
                "type": "control_cycle",
                "cycle_id": cycle_num,
                "cycle_id_str": cycle.cycle_id,
                "timestamp": cycle.timestamp,
                "portal_id": cycle.portal_id,
                "phase": phase,
                "action": cycle.recommended_action,
                "safety_decision": cycle.safety_decision,
                "actuation_status": cycle.actuation_status,
                "recovery_state": cycle.recovery_state,
                "health_score": cycle.health_score,
                "consensus_state": cycle.consensus_state,
                "human_approval_required": cycle.human_approval_required,
            })

            # 2. forecast
            STREAM_BROADCASTER.publish_forecast({
                "type": "forecast",
                "timestamp": cycle.timestamp,
                "portal_id": cycle.portal_id,
                "safe_capacity": cycle.forecast.get("safe_capacity", 13200),
                "predicted_cpu": cycle.forecast.get("predicted_cpu", 25.0),
                "predicted_latency_p95": cycle.forecast.get("predicted_latency_p95", 120.0),
                "capacity_pressure_index": cycle.forecast.get("capacity_pressure_index", 0.0),
                "now": cycle.pre_metrics.get("virtual_users", 12481) if cycle.pre_metrics else 12481,
                "time_to_breach_minutes": cycle.forecast.get("time_to_breach_minutes", 7.0),
                "breach_time": cycle.forecast.get("breach_time", "BREACH IN ~7 MIN"),
                "horizons": {
                    "5m": cycle.forecast.get("5m_forecast"),
                    "10m": cycle.forecast.get("10m_forecast"),
                    "15m": cycle.forecast.get("15m_forecast"),
                },
            })

            # 3. anomaly
            STREAM_BROADCASTER.publish_anomaly({
                "type": "anomaly",
                "timestamp": cycle.timestamp,
                "portal_id": cycle.portal_id,
                "is_anomaly": cycle.anomaly.get("is_anomaly", False),
                "anomaly_score": cycle.anomaly.get("anomaly_score", 0.0),
                "severity": cycle.anomaly.get("severity", "LOW"),
                "contributing_features": cycle.anomaly.get("contributing_features", []),
                "top_contributors": cycle.anomaly.get("contributing_features") or ["DB connections", "Latency", "Queue depth"],
            })

            # 4. rca
            STREAM_BROADCASTER.publish_rca({
                "type": "rca",
                "timestamp": cycle.timestamp,
                "portal_id": cycle.portal_id,
                "root_cause": cycle.rca.get("rca_class", "NORMAL"),
                "confidence": cycle.rca.get("confidence", 1.0),
                "causal_path": cycle.causal_path or ["Traffic", "API", "DB Pool 🔴", "Query Wait", "Latency", "503"],
                "probabilities": cycle.rca.get("probabilities", {}),
                "breakdown": cycle.rca.get("probabilities", {}),
                "recommended_mitigation": cycle.rca.get("recommended_mitigation", ""),
            })

            # 5. action
            STREAM_BROADCASTER.publish_action({
                "type": "action",
                "timestamp": cycle.timestamp,
                "portal_id": cycle.portal_id,
                "action": cycle.recommended_action,
                "confidence": cycle.action_recommendation.get("confidence", 1.0),
                "human_approval_required": cycle.human_approval_required,
                "parameters": cycle.action_recommendation.get("parameters", {}),
                "all_action_probabilities": cycle.action_recommendation.get("all_action_probabilities", {}),
            })

            # 6. safety
            STREAM_BROADCASTER.publish_safety({
                "type": "safety",
                "timestamp": cycle.timestamp,
                "portal_id": cycle.portal_id,
                "decision": cycle.safety_decision,
                "is_safe": cycle.safety_validation.get("is_safe", True),
                "consensus_state": cycle.consensus_state,
                "rejection_reasons": cycle.safety_validation.get("rejection_reasons", []),
                "cooldown_remaining_sec": cycle.safety_validation.get("cooldown_remaining_sec", 0),
            })

            # 7. actuation (Module 9: Actuator Stabilization Trajectory)
            STREAM_BROADCASTER.publish_actuation({
                "type": "actuation",
                "cycle_id": cycle.cycle_id,
                "timestamp": cycle.timestamp,
                "portal_id": cycle.portal_id,
                "status": cycle.actuation_status,
                "action": cycle.recommended_action,
                "environment": cycle.actuator_env,
                "verification_status": cycle.verification_status,
                "recovery_score": cycle.recovery_score,
                "recovery_state": cycle.recovery_state,
                "why": cycle.rca.get("rca_class") or cycle.rca.get("root_cause") or "DB saturation",
                "confidence": cycle.action_recommendation.get("confidence", 0.972),
                "metric_deltas": cycle.metric_deltas or (cycle.actuation.get("metric_deltas") if cycle.actuation else []),
                "stabilization_trajectory": cycle.stabilization_trajectory or (cycle.actuation.get("stabilization_trajectory") if cycle.actuation else []),
                "before_metrics": cycle.before_metrics or cycle.pre_metrics or {},
                "after_metrics": cycle.after_metrics or cycle.post_metrics or {},
                "actuation_record": cycle.actuation or {},
            })

            # 8. warnings & recoveries (Module 8: Telemetry-Driven Warning Engine)
            new_warns, recs = WARNING_ENGINE.evaluate(cycle)
            for w in new_warns:
                w_dict = w.to_dict()
                w_dict["type"] = "warning"
                w_dict["portal_id"] = cycle.portal_id
                w_dict["cycle_id"] = cycle.cycle_id
                STREAM_BROADCASTER.publish_warning(w_dict)
            for r in recs:
                r["type"] = "recovery"
                r["portal_id"] = cycle.portal_id
                r["cycle_id"] = cycle.cycle_id
                r["verification_status"] = "METRIC_NORMALIZED"
                r["recovery_state"] = cycle.recovery_state
                STREAM_BROADCASTER.publish_recovery(r)

            # Fallback warning if health is degraded and no specific spec matched
            if os.getenv("PORTALPULSE_DEMO_MODE") != "1" and not new_warns and (cycle.anomaly.get("is_anomaly") or cycle.health_score < 75.0 or cycle.safety_decision == "REJECTED"):
                STREAM_BROADCASTER.publish_warning({
                    "type": "warning",
                    "id": "WARN_HEALTH_DEGRADED",
                    "title": "SYSTEM HEALTH DEGRADED",
                    "timestamp": cycle.timestamp,
                    "portal_id": cycle.portal_id,
                    "code": "ANOMALY_DETECTED" if cycle.anomaly.get("is_anomaly") else "HEALTH_DEGRADED",
                    "message": f"SRE condition: {cycle.rca.get('rca_class', 'anomaly')} (health {cycle.health_score}%)",
                    "severity": cycle.anomaly.get("severity", "WARNING"),
                    "trigger_condition": "Health score < 75% or anomaly detected",
                    "current_metric": f"{cycle.health_score}% Health",
                    "threshold": "75% Health",
                    "recommended_action": cycle.recommended_action,
                    "remediation_state": cycle.actuation_status,
                    "recovery_state": cycle.recovery_state,
                    "what_happened": "Anomaly detected in system telemetry.",
                    "why_it_happened": f"RCA attributed to {cycle.rca.get('rca_class', 'anomaly')}.",
                    "what_portalpulse_did": f"M5 recommended {cycle.recommended_action}.",
                    "current_result": f"Actuation state: {cycle.actuation_status}.",
                })

            # 9. Report autonomous recovery only when M7 ran and post-action
            # measurements actually passed verification. Nominal NO_OP cycles
            # and threshold-only clearances are not M7 recoveries.
            if cycle.verification_status == "RECOVERY_VERIFIED" and cycle.actuation_status == "EXECUTED" and cycle.post_metrics:
                STREAM_BROADCASTER.publish_recovery({
                    "type": "recovery",
                    "id": "REC_STABILIZED",
                    "title": "M7 POST-ACTION CHECK PASSED",
                    "severity": "RECOVERY",
                    "timestamp": cycle.timestamp,
                    "portal_id": cycle.portal_id,
                    "recovery_state": cycle.recovery_state,
                    "recovery_score": cycle.recovery_score or 100.0,
                    "verification_status": cycle.verification_status,
                    "pre_p95_ms": cycle.pre_metrics.get("p95_ms", 0) if cycle.pre_metrics else 0,
                    "post_p95_ms": cycle.post_metrics.get("p95_ms", 0) if cycle.post_metrics else 0,
                    "message": "The post-action sample passed verification; later cycles continue monitoring the injected pressure.",
                    "current_result": f"p95 {cycle.pre_metrics['p95_ms']/1000.0:.2f}s → {cycle.post_metrics['p95_ms']/1000.0:.2f}s",
                    "what_happened": "The measured post-action sample passed the verifier for this cycle.",
                    "why_it_happened": "M7 executed the safety-approved local action and the verifier checked the next sample.",
                    "what_portalpulse_did": f"M7 executed {cycle.recommended_action}; this cycle passed verification. Ongoing pressure is monitored separately.",
                })
        except Exception as exc:
            logger.debug(f"[CONTROL_LOOP] Non-blocking SSE broadcast ignored: {exc}")

    def get_status(self) -> ControlLoopStatus:
        """Return the current lifecycle and operational status of the control loop."""
        return ControlLoopStatus(
            running=self.running,
            cycle_id=self.cycle_id,
            interval_ms=self.interval_ms,
            last_cycle=self.last_cycle,
            next_cycle=self.next_cycle,
            phase=self.phase,
            current_action=self.current_action,
            recovery_state=self.recovery_state,
            last_error=self.last_error,
        )

    def get_latest(self) -> Dict[str, Any]:
        """Return the complete latest ControlCycle."""
        if self.history:
            return self.history[-1].model_dump()
        if EXPLAINABLE_PIPELINE.last_cycle:
            return EXPLAINABLE_PIPELINE.last_cycle.model_dump()
        # If no cycle has run yet, trigger one synchronously
        cycle = self.step()
        return cycle.model_dump()

    def get_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Return recent cycles."""
        cycles = list(self.history)
        if not cycles and EXPLAINABLE_PIPELINE.cycle_history:
            cycles = list(EXPLAINABLE_PIPELINE.cycle_history)
        selected = cycles[-limit:] if cycles else []
        return [c.model_dump() for c in selected]


CONTROL_LOOP = ContinuousControlLoop(interval_seconds=3.0)

router = APIRouter(prefix="/api/v1/control-loop", tags=["Continuous Control Loop"])
alias_router = APIRouter(prefix="/control-loop", tags=["Continuous Control Loop"])


@router.get("/status", response_model=ControlLoopStatus, summary="Continuous Control Loop Status")
@alias_router.get("/status", response_model=ControlLoopStatus, summary="Continuous Control Loop Status")
def get_control_loop_status() -> ControlLoopStatus:
    return CONTROL_LOOP.get_status()


@router.get("/latest", summary="Get Latest Autonomous Control Cycle")
@alias_router.get("/latest", summary="Get Latest Autonomous Control Cycle")
def get_control_loop_latest() -> Dict[str, Any]:
    return CONTROL_LOOP.get_latest()


@router.get("/history", summary="Get Autonomous Control Cycle History")
@alias_router.get("/history", summary="Get Autonomous Control Cycle History")
def get_control_loop_history(limit: int = Query(default=50, ge=1, le=200)) -> List[Dict[str, Any]]:
    return CONTROL_LOOP.get_history(limit=limit)
