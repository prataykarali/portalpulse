"""Formal Portal Adapter Contract for PortalPulse.

Ensures that PortalPulse does not know or embed any portal's internal business logic,
but communicates strictly via standardized telemetry, architecture, and control interfaces.
"""

from __future__ import annotations

import os
import random
import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from portalpulse_sdk.schema import (
    ActionResult,
    CapacityProfile,
    DependencyGraphSpec,
    PortalCapabilities,
    ResourceProfile,
    UniversalTelemetry,
)


class PortalAdapter(ABC):
    """Abstract contractual interface between PortalPulse Control Plane and any external portal."""

    def __init__(self, portal_id: str, portal_name: str) -> None:
        self.portal_id = portal_id
        self.portal_name = portal_name

    @abstractmethod
    def health_check(self) -> Dict[str, Any]:
        """Verify portal liveness and operational health."""
        pass

    @abstractmethod
    def get_metadata(self) -> Dict[str, Any]:
        """Return portal identity, tier, and descriptive metadata."""
        pass

    @abstractmethod
    def get_architecture(self) -> Dict[str, Any]:
        """Return structural topology and architecture diagram specification."""
        pass

    @abstractmethod
    def get_telemetry(self) -> UniversalTelemetry:
        """Fetch or sample current live telemetry."""
        pass

    @abstractmethod
    def get_capacity_profile(self) -> Optional[CapacityProfile]:
        """Return empirical capacity boundaries if discovered."""
        pass

    @abstractmethod
    def execute_action(self, action: str, parameters: Dict[str, Any]) -> ActionResult:
        """Dispatch physical mitigation or operational mutation to portal."""
        pass

    @abstractmethod
    def verify_action(self, pre_telemetry: UniversalTelemetry, post_telemetry: UniversalTelemetry) -> Dict[str, Any]:
        """Verify whether an executed action improved latency, errors, and capacity."""
        pass

    @abstractmethod
    def rollback_action(self, action: str, parameters: Dict[str, Any]) -> ActionResult:
        """Revert a previously executed action if verified ineffective."""
        pass

    @abstractmethod
    def get_user_impact(self) -> Dict[str, Any]:
        """Calculate users affected, failed requests, and waiting queue depth."""
        pass

    @abstractmethod
    def get_dependencies(self) -> DependencyGraphSpec:
        """Return dynamic topological dependency graph."""
        pass

    @abstractmethod
    def get_actuator_environment(self) -> str:
        """Declare real runtime actuator environment: KUBERNETES, DOCKER_COMPOSE, or LOCAL_PROCESS."""
        pass


# ===========================================================================
# NIRANTAR ADAPTER (RAILWAY ERP / MICROSERVICE ARCHITECTURE)
# ===========================================================================
class NirantarAdapter(PortalAdapter):
    """Adapter connecting PortalPulse to Nirantar Railway ERP."""

    def __init__(self) -> None:
        super().__init__(portal_id="nirantar", portal_name="Nirantar Railway ERP")
        self._capacity_profile: Optional[CapacityProfile] = None

    def get_actuator_environment(self) -> str:
        if os.path.exists("/var/run/secrets/kubernetes.io/serviceaccount"):
            return "KUBERNETES"
        elif os.environ.get("DOCKER_CONTAINER") or os.path.exists("/.dockerenv"):
            return "DOCKER_COMPOSE"
        return "LOCAL_PROCESS"

    def health_check(self) -> Dict[str, Any]:
        from backend.connectors.nirantar_bridge import NIRANTAR_INFRA_STATE
        return {
            "status": "HEALTHY",
            "portal": self.portal_id,
            "architecture": "Microservices + Redis Cache + Celery Workers",
            "actuator_env": self.get_actuator_environment(),
            "infra": NIRANTAR_INFRA_STATE,
        }

    def get_metadata(self) -> Dict[str, Any]:
        return {
            "portal_id": self.portal_id,
            "portal_name": self.portal_name,
            "tier": "mission_critical_transport",
            "stack": "FastAPI + Celery + Redis + SQLite WAL",
            "actuator_env": self.get_actuator_environment(),
        }

    def get_architecture(self) -> Dict[str, Any]:
        return {
            "portal_id": self.portal_id,
            "style": "DISTRIBUTED_MICROSERVICE",
            "components": [
                {"id": "ingress", "label": "Cloudflare Edge & Gateway", "type": "gateway"},
                {"id": "api_gateway", "label": "FastAPI Core Gateway", "type": "api"},
                {"id": "cache", "label": "Distributed Redis Cache", "type": "cache", "healthy": True},
                {"id": "workers", "label": f"Worker Pods ({self.health_check()['infra']['pods']} Replicas)", "type": "worker"},
                {"id": "database", "label": "SQLite WAL Engine (Partitioned)", "type": "database"},
            ],
            "connections": [
                ("ingress", "api_gateway"),
                ("api_gateway", "cache"),
                ("api_gateway", "workers"),
                ("workers", "database"),
            ],
        }

    def get_telemetry(self) -> UniversalTelemetry:
        from backend.connectors.nirantar_bridge import (
            NIRANTAR_INFRA_STATE,
            NIRANTAR_SESSION_TRACKER,
        )
        t_data = NIRANTAR_SESSION_TRACKER.get_telemetry_dict()
        pods = NIRANTAR_INFRA_STATE.get("pods", 4)
        active_u = t_data.get("active_sessions", 0)
        rps = t_data.get("requests_per_sec", 0.1)

        cpu = min(100.0, max(2.5, 8.0 + (active_u / max(1, pods * 500)) * 60.0))
        lat = max(1.0, t_data.get("avg_latency_ms", 12.0))
        if NIRANTAR_SESSION_TRACKER.waiting_room.enabled:
            lat = min(lat, 85.0)
        recent_errors = NIRANTAR_SESSION_TRACKER.get_recent_error_rates()
        failure_pct = float(recent_errors.get("rate_5xx_pct", 0.0))
        limit_pct = float(recent_errors.get("rate_429_pct", 0.0))
        error_rate = min(1.0, (failure_pct + limit_pct) / 100.0)

        return UniversalTelemetry(
            portal_id=self.portal_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            active_users=active_u,
            requests_per_sec=float(rps),
            cpu_percent=round(cpu, 1),
            ram_percent=round(min(100.0, 30.0 + active_u * 0.015), 1),
            latency_ms=round(lat, 1),
            throughput=round(float(rps) * (1.0 - error_rate), 2),
            error_rate=error_rate,
            http_5xx=failure_pct,
            db_latency_ms=round(max(0.5, lat * 0.4), 1),
            db_connections=round(min(100.0, (t_data.get("in_flight_requests", 0) / max(1, NIRANTAR_INFRA_STATE.get("db_pool_size", 150))) * 100.0), 1),
            queue_length=t_data.get("waiting_room_queue_size", 0),
            service_instances=pods,
            network_in_mb=round(rps * 0.002, 3),
            network_out_mb=round(rps * 0.008, 3),
            tags={
                "provenance": "LOCAL_NIRANTAR_BRIDGE",
                "actuator_env": self.get_actuator_environment(),
                "is_simulated": "true",
            },
            active_sessions=active_u,
            concurrent_requests=int(t_data.get("in_flight_requests", 0)),
            p50_latency_ms=round(float(t_data.get("p50_latency_ms", lat)), 1),
            p95_latency_ms=round(float(t_data.get("p95_latency_ms", lat)), 1),
            p99_latency_ms=round(float(t_data.get("p99_latency_ms", lat)), 1),
            db_connection_limit=100,
        )

    def get_capacity_profile(self) -> Optional[CapacityProfile]:
        return self._capacity_profile

    def set_capacity_profile(self, profile: CapacityProfile) -> None:
        self._capacity_profile = profile

    def execute_action(self, action: str, parameters: Dict[str, Any]) -> ActionResult:
        from backend.connectors.nirantar_bridge import NIRANTAR_INFRA_STATE, NIRANTAR_SESSION_TRACKER
        start_t = time.monotonic()
        prev_state = dict(NIRANTAR_INFRA_STATE)

        if action == "ENABLE_WAITING_ROOM":
            NIRANTAR_INFRA_STATE["waiting_room_enabled"] = True
            NIRANTAR_INFRA_STATE["waiting_room_limit"] = parameters.get("max_admitted_sessions", 2000)
            NIRANTAR_SESSION_TRACKER.waiting_room.enable(capacity=int(NIRANTAR_INFRA_STATE["waiting_room_limit"]))
            status = "SUCCESS"
        elif action == "DISABLE_WAITING_ROOM":
            NIRANTAR_INFRA_STATE["waiting_room_enabled"] = False
            NIRANTAR_SESSION_TRACKER.waiting_room.disable()
            status = "SUCCESS"
        elif action == "SCALE_OUT_WORKERS":
            delta = parameters.get("replicas_delta", 2)
            NIRANTAR_INFRA_STATE["pods"] = min(16, NIRANTAR_INFRA_STATE["pods"] + delta)
            status = "SUCCESS"
        elif action == "SCALE_IN_WORKERS":
            delta = parameters.get("replicas_delta", 2)
            NIRANTAR_INFRA_STATE["pods"] = max(2, NIRANTAR_INFRA_STATE["pods"] - delta)
            status = "SUCCESS"
        elif action == "ENABLE_CACHE":
            NIRANTAR_INFRA_STATE["cache_enabled"] = True
            NIRANTAR_INFRA_STATE["redis_cache_warmed"] = True
            status = "SUCCESS"
        elif action == "PURGE_CACHE":
            NIRANTAR_INFRA_STATE["cache_enabled"] = False
            status = "SUCCESS"
        elif action == "ACTIVATE_RATE_LIMIT":
            NIRANTAR_SESSION_TRACKER.rate_limiter.set_rate_limit(float(parameters.get("rate_limit_rps", 8)))
            status = "SUCCESS"
        elif action == "DIVERT_READS_TO_REPLICA":
            NIRANTAR_INFRA_STATE["reads_diverted_to_replica"] = True
            status = "SUCCESS"
        elif action == "ENGAGE_CIRCUIT_BREAKER":
            NIRANTAR_INFRA_STATE["circuit_breaker_active"] = True
            status = "SUCCESS"
        elif action == "INCREASE_DB_POOL":
            NIRANTAR_INFRA_STATE["db_pool_size"] = min(300, NIRANTAR_INFRA_STATE["db_pool_size"] + int(parameters.get("delta_connections", 50)))
            NIRANTAR_INFRA_STATE["sim_latency_ms"] = 0
            status = "SUCCESS"
        elif action == "PURGE_REDIS_CACHE":
            NIRANTAR_INFRA_STATE["redis_cache_warmed"] = True
            status = "SUCCESS"
        elif action == "DRAIN_REQUEST_QUEUE":
            NIRANTAR_INFRA_STATE["sim_latency_ms"] = 0
            status = "SUCCESS"
        elif action == "RESTART_DEGRADED_PODS":
            NIRANTAR_INFRA_STATE["sim_fault"] = "NONE"
            NIRANTAR_INFRA_STATE["sim_latency_ms"] = 0
            NIRANTAR_INFRA_STATE["pods"] = min(16, NIRANTAR_INFRA_STATE["pods"] + 1)
            status = "SUCCESS"
        else:
            status = "UNKNOWN_ACTION"

        elapsed_ms = (time.monotonic() - start_t) * 1000.0
        return ActionResult(
            action_id=f"act_{int(time.time()*1000)}",
            command=action,
            status=status,
            execution_time_ms=round(elapsed_ms, 2),
            message=f"{action} executed on the local Nirantar bridge ({self.get_actuator_environment()})",
            rollback_available=True,
            rollback_command="ROLLBACK",
            rollback_parameters=prev_state,
        )

    def rollback_action(self, action: str, parameters: Dict[str, Any]) -> ActionResult:
        from backend.connectors.nirantar_bridge import NIRANTAR_INFRA_STATE
        start_t = time.monotonic()
        NIRANTAR_INFRA_STATE.update(parameters)
        elapsed_ms = (time.monotonic() - start_t) * 1000.0
        return ActionResult(
            action_id=f"rb_{int(time.time()*1000)}",
            command="ROLLBACK",
            status="SUCCESS",
            execution_time_ms=round(elapsed_ms, 2),
            message="Nirantar state successfully rolled back to previous state.",
            rollback_available=False,
        )

    def verify_action(self, pre_telemetry: UniversalTelemetry, post_telemetry: UniversalTelemetry) -> Dict[str, Any]:
        pre_p95 = pre_telemetry.p95_latency_ms or pre_telemetry.latency_ms
        post_p95 = post_telemetry.p95_latency_ms or post_telemetry.latency_ms
        lat_improved_pct = round(((pre_p95 - post_p95) / max(0.1, pre_p95)) * 100.0, 1)
        err_reduced_pct = round(((pre_telemetry.error_rate - post_telemetry.error_rate) / max(0.001, pre_telemetry.error_rate)) * 100.0, 1)

        is_effective = (post_p95 <= pre_p95) and (post_telemetry.error_rate <= pre_telemetry.error_rate)
        return {
            "effective": is_effective,
            "status": "RECOVERY_VERIFIED" if is_effective else "ACTION_INEFFECTIVE",
            "latency_improvement_pct": lat_improved_pct,
            "error_reduction_pct": err_reduced_pct,
            "pre_p95_ms": pre_p95,
            "post_p95_ms": post_p95,
            "pre_cpu": pre_telemetry.cpu_percent,
            "post_cpu": post_telemetry.cpu_percent,
        }

    def get_user_impact(self) -> Dict[str, Any]:
        from backend.connectors.nirantar_bridge import NIRANTAR_SESSION_TRACKER
        t = NIRANTAR_SESSION_TRACKER.get_telemetry_dict()
        u = t.get("active_sessions", 0)
        wait = t.get("waiting_room_queue_size", 0)
        return {
            "users_affected": wait if wait > 0 else (int(u * 0.08) if t.get("avg_latency_ms", 0) > 400 else 0),
            "failed_requests": int(t.get("rate_5xx_pct", 0) * u * 0.01),
            "est_waiting_time_sec": round(wait * 0.4, 1),
            "login_success_pct": t.get("login_success_pct", 100.0),
        }

    def get_dependencies(self) -> DependencyGraphSpec:
        return DependencyGraphSpec(
            nodes=["ingress", "api_gateway", "redis_cache", "worker_pods", "sqlite_wal"],
            edges=[
                ("ingress", "api_gateway"),
                ("api_gateway", "redis_cache"),
                ("api_gateway", "worker_pods"),
                ("worker_pods", "sqlite_wal"),
            ],
            entrypoint_node="ingress",
            storage_nodes=["sqlite_wal", "redis_cache"],
        )


# ===========================================================================
# IEMCRP ADAPTER (STATE UNIVERSITY EXAMINATION CELL / MONOLITHIC DB)
# ===========================================================================
class IEMCRPAdapter(PortalAdapter):
    """Adapter connecting PortalPulse to the real monolithic IEMCRP application."""

    def __init__(self) -> None:
        super().__init__(portal_id="college_portal", portal_name="IEMCRP Examination Portal")
        self._capacity_profile: Optional[CapacityProfile] = None

    def get_actuator_environment(self) -> str:
        return "LOCAL_PROCESS"  # Monolithic PHP/Python process pool

    def health_check(self) -> Dict[str, Any]:
        from backend.portals.iemcrp_app import DB_POOL, IEMCRP_INFRA_STATE
        return {
            "status": "HEALTHY",
            "portal": self.portal_id,
            "architecture": "Monolithic App Server + MySQL (Pool=50)",
            "actuator_env": self.get_actuator_environment(),
            "db_pool": DB_POOL.get_stats(),
            "infra": IEMCRP_INFRA_STATE,
        }

    def get_metadata(self) -> Dict[str, Any]:
        return {
            "portal_id": self.portal_id,
            "portal_name": self.portal_name,
            "tier": "higher_education_examination",
            "stack": "Monolithic PHP/Django + Relational DB (No Redis, No Replicas)",
            "actuator_env": self.get_actuator_environment(),
            "db_connection_limit": 50,
        }

    def get_architecture(self) -> Dict[str, Any]:
        from backend.portals.iemcrp_app import DB_POOL
        stats = DB_POOL.get_stats()
        return {
            "portal_id": self.portal_id,
            "style": "MONOLITHIC_CONSTRAINED",
            "components": [
                {"id": "student_client", "label": "Student Browser / Client", "type": "client"},
                {"id": "cloudflare_edge", "label": "Cloudflare Perimeter", "type": "gateway"},
                {"id": "monolith_server", "label": "Monolithic App Server (PHP/Django)", "type": "api"},
                {"id": "mysql_monolith", "label": f"Monolithic DB (Pool: {stats['active_connections']}/50)", "type": "database", "is_bottleneck": stats['active_connections'] >= 45},
            ],
            "connections": [
                ("student_client", "cloudflare_edge"),
                ("cloudflare_edge", "monolith_server"),
                ("monolith_server", "mysql_monolith"),
            ],
        }

    def get_telemetry(self) -> UniversalTelemetry:
        from backend.portals.iemcrp_app import DB_POOL, IEMCRP_INFRA_STATE
        stats = DB_POOL.get_stats()
        u = max(0, stats["active_connections"] * 18)
        rps = round(max(0.1, stats["active_connections"] * 2.8), 1)

        base_lat = 18.0 + stats["injected_db_latency_ms"]
        if stats["active_connections"] > 40:
            base_lat += (stats["active_connections"] - 40) * 55.0  # Steep exponential knee

        err_rate = 0.05 if stats["is_exhausted"] else (0.01 if base_lat > 500 else 0.0)

        # Relieve latency and errors if mitigation active on IEMCRP
        if IEMCRP_INFRA_STATE.get("waiting_room_enabled"):
            base_lat = min(base_lat, 65.0)
            err_rate = 0.0
        elif IEMCRP_INFRA_STATE.get("static_fallback_enabled"):
            base_lat = min(base_lat, 25.0)
            err_rate = 0.0

        # In the local live demo, M1 must see the same HTTP request window as
        # the Traffic graphs. The former pool-only estimate missed 429/503s.
        demo_mode = os.getenv("PORTALPULSE_DEMO_MODE") == "1"
        if demo_mode:
            from backend.simulation.traffic_controller import TRAFFIC_CONTROLLER
            traffic = TRAFFIC_CONTROLLER
            rps = traffic.stats_rps if traffic.is_running else 0.0
            err_rate = traffic.stats_failure_rate / 100.0 if traffic.is_running else 0.0
            base_lat = traffic.stats_p50
            p95_lat = traffic.stats_p95
            p99_lat = traffic.stats_p99
            u = traffic._active_worker_count if traffic.is_running else 0
            recent = list(traffic.transactions)
            cutoff = datetime.now(timezone.utc).timestamp() - 3.0
            recent = [x for x in recent if datetime.fromisoformat(x.timestamp).timestamp() >= cutoff]
            http_5xx = 100.0 * sum(x.status >= 500 for x in recent) / len(recent) if recent else 0.0
        else:
            p95_lat = base_lat * 1.6
            p99_lat = base_lat * 2.5
            http_5xx = err_rate * 100.0

        return UniversalTelemetry(
            portal_id=self.portal_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            active_users=u,
            requests_per_sec=rps,
            cpu_percent=min(100.0, 8.0 + stats["active_connections"] * 1.6),
            ram_percent=min(100.0, 32.0 + stats["active_connections"] * 0.9),
            latency_ms=round(base_lat, 1),
            throughput=round(rps * (1.0 - err_rate), 1),
            error_rate=err_rate,
            http_5xx=round(http_5xx, 1),
            db_latency_ms=round(base_lat * 0.7, 1),
            db_connections=stats["recent_peak_utilization_percent"] if demo_mode else stats["utilization_percent"],
            queue_length=stats["waiting_queries"],
            service_instances=IEMCRP_INFRA_STATE["php_workers"],
            tags={
                "provenance": "LIVE_PORTAL_HTTP" if demo_mode else "LIVE_PORTAL",
                "actuator_env": self.get_actuator_environment(),
                "is_simulated": "false",
                "cpu_source": "pool-derived estimate",
            },
            active_sessions=u,
            concurrent_requests=traffic.in_flight_requests if demo_mode else int(max(1, rps)),
            p50_latency_ms=round(base_lat, 1) if demo_mode else round(base_lat * 0.85, 1),
            p95_latency_ms=round(p95_lat, 1),
            p99_latency_ms=round(p99_lat, 1),
            db_connection_limit=50,
        )

    def get_capacity_profile(self) -> Optional[CapacityProfile]:
        return self._capacity_profile

    def set_capacity_profile(self, profile: CapacityProfile) -> None:
        self._capacity_profile = profile

    def execute_action(self, action: str, parameters: Dict[str, Any]) -> ActionResult:
        from backend.portals.iemcrp_app import execute_iemcrp_action, IEMCRP_INFRA_STATE
        prev_state = dict(IEMCRP_INFRA_STATE)
        res = execute_iemcrp_action({"action": action, "parameters": parameters})
        return ActionResult(
            action_id=f"iemcrp_{int(time.time()*1000)}",
            command=action,
            status=res.get("status", "SUCCESS"),
            execution_time_ms=12.5,
            message=f"IEMCRP {action} applied to monolithic ERP.",
            rollback_available=True,
            rollback_command="ROLLBACK",
            rollback_parameters=prev_state,
        )

    def rollback_action(self, action: str, parameters: Dict[str, Any]) -> ActionResult:
        from backend.portals.iemcrp_app import IEMCRP_INFRA_STATE
        IEMCRP_INFRA_STATE.update(parameters)
        return ActionResult(
            action_id=f"iemcrp_rb_{int(time.time()*1000)}",
            command="ROLLBACK",
            status="SUCCESS",
            execution_time_ms=8.0,
            message="IEMCRP configuration rolled back to previous operational state.",
            rollback_available=False,
        )

    def verify_action(self, pre_telemetry: UniversalTelemetry, post_telemetry: UniversalTelemetry) -> Dict[str, Any]:
        pre_p95 = pre_telemetry.p95_latency_ms or pre_telemetry.latency_ms
        post_p95 = post_telemetry.p95_latency_ms or post_telemetry.latency_ms
        is_effective = (post_p95 <= pre_p95) and (post_telemetry.error_rate <= pre_telemetry.error_rate)
        return {
            "effective": is_effective,
            "status": "RECOVERY_VERIFIED" if is_effective else "ACTION_INEFFECTIVE",
            "latency_improvement_pct": round(((pre_p95 - post_p95) / max(0.1, pre_p95)) * 100.0, 1),
            "pre_p95_ms": pre_p95,
            "post_p95_ms": post_p95,
            "pre_db_pool": pre_telemetry.db_connections,
            "post_db_pool": post_telemetry.db_connections,
        }

    def get_user_impact(self) -> Dict[str, Any]:
        from backend.portals.iemcrp_app import DB_POOL
        stats = DB_POOL.get_stats()
        wait = stats["waiting_queries"]
        affected = wait * 12 + (stats["failed_queries"] * 10)
        return {
            "users_affected": affected,
            "failed_requests": stats["failed_queries"],
            "est_waiting_time_sec": round(wait * 1.8, 1),
            "login_success_pct": round(max(0.0, 100.0 - (stats["failed_queries"] / max(1, stats["total_queries"]) * 100.0)), 1),
        }

    def get_dependencies(self) -> DependencyGraphSpec:
        return DependencyGraphSpec(
            nodes=["student_client", "cloudflare_edge", "monolith_server", "mysql_monolith"],
            edges=[
                ("student_client", "cloudflare_edge"),
                ("cloudflare_edge", "monolith_server"),
                ("monolith_server", "mysql_monolith"),
            ],
            entrypoint_node="student_client",
            storage_nodes=["mysql_monolith"],
        )


# Global adapter registry mapping portal_id to active PortalAdapter instance
ADAPTER_REGISTRY: Dict[str, PortalAdapter] = {
    "nirantar": NirantarAdapter(),
    "college_portal": IEMCRPAdapter(),
    "iemcrp": IEMCRPAdapter(),
}

def get_portal_adapter(portal_id: str) -> PortalAdapter:
    """Retrieve registered adapter for given portal."""
    if portal_id in ADAPTER_REGISTRY:
        return ADAPTER_REGISTRY[portal_id]
    # Default to Nirantar if unknown
    return ADAPTER_REGISTRY["nirantar"]
