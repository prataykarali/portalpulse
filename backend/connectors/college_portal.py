"""Reference Connector for College / University ERP & Exam Results Portal.

Demonstrates a constrained infrastructure profile where database replicas and
distributed caches are NOT supported (e.g. monolithic MySQL + PHP/Django backend).
Demonstrates how ActionMasker automatically suppresses unsupported actions.
"""

from __future__ import annotations

import random
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from portalpulse_sdk.discovery import discover_resource_envelope
from portalpulse_sdk.interface import BasePortalConnector
from portalpulse_sdk.middleware import GLOBAL_SESSION_TRACKER
from portalpulse_sdk.schema import (
    ActionCommand,
    ActionResult,
    CapacityProfile,
    DependencyGraphSpec,
    PortalCapabilities,
    ResourceProfile,
    UniversalTelemetry,
)


class CollegePortalConnector(BasePortalConnector):
    """Connector for an educational university ERP with constrained infrastructure."""

    def __init__(self) -> None:
        super().__init__(portal_id="college_portal", portal_name="State University Exam Results Portal")
        self.php_workers: int = 4
        self.static_fallback_enabled: bool = False
        self.waiting_room_active: bool = False
        self.simulation_mode: bool = False
        self._latest_capacity_profile: Optional[CapacityProfile] = None

    def get_resources(self) -> ResourceProfile:
        """Discover College Portal's real host hardware and constrained process limits."""
        return discover_resource_envelope(
            portal_id=self.portal_id,
            worker_count=self.php_workers,
            worker_concurrency=16,
            db_pool_size=40,
            db_connection_limit=50,
            service_instances=self.php_workers,
            max_service_instances=16,
        )

    def get_capacity_profile(self) -> Optional[CapacityProfile]:
        return self._latest_capacity_profile

    def set_capacity_profile(self, profile: CapacityProfile) -> None:
        self._latest_capacity_profile = profile

    def get_capabilities(self) -> PortalCapabilities:
        """Educational portal with NO database replicas and NO Redis cache."""
        return PortalCapabilities(
            horizontal_scaling=True,
            vertical_scaling=False,
            caching=False,  # <--- NO Redis deployed!
            static_fallback=True,
            rate_limiting=True,
            request_queue=True,
            database_replica=False,  # <--- Monolithic MySQL, NO replica!
            database_pool_scaling=False,
            circuit_breaker=True,
            pod_restart=True,
            waiting_room=True,
            feature_flags=False,
            min_instances=2,
            max_instances=16,
        )

    def get_dependencies(self) -> DependencyGraphSpec:
        """4-tier architecture (No cache tier)."""
        return DependencyGraphSpec(
            nodes=[
                "student_client",
                "cloudflare_edge",
                "php_app_server",
                "mysql_monolith",
            ],
            edges=[
                ("student_client", "cloudflare_edge"),
                ("cloudflare_edge", "php_app_server"),
                ("php_app_server", "mysql_monolith"),
            ],
            entrypoint_node="student_client",
            storage_nodes=["mysql_monolith"],
        )

    def get_health(self) -> Dict[str, Any]:
        """Local health check report."""
        return {
            "status": "HEALTHY",
            "php_workers": self.php_workers,
            "static_fallback_enabled": self.static_fallback_enabled,
            "waiting_room_active": self.waiting_room_active,
            "has_replica": False,
            "has_redis": False,
            "simulation_mode": self.simulation_mode,
        }

    def get_telemetry(self) -> UniversalTelemetry:
        """Fetch live telemetry from the independent IEMCRP application via its adapter."""
        from backend.control_plane.portal_adapter import get_portal_adapter
        adapter = get_portal_adapter("college_portal")
        return adapter.get_telemetry()

    def execute_action(self, command: ActionCommand) -> ActionResult:
        """Execute action via IEMCRPAdapter or reject unsupported infrastructure calls."""
        from backend.control_plane.portal_adapter import get_portal_adapter
        adapter = get_portal_adapter("college_portal")
        action = command.action_type
        params = command.parameters

        if action in ("DIVERT_READS_TO_REPLICA", "PURGE_REDIS_CACHE"):
            return ActionResult(
                action_id=command.action_id,
                portal_id=self.portal_id,
                success=False,
                message=f"REJECTED: College portal has no {action.lower()} capabilities.",
            )

        if action == "ENABLE_WAITING_ROOM":
            self.waiting_room_active = True
        elif action == "DISABLE_WAITING_ROOM":
            self.waiting_room_active = False

        res = adapter.execute_action(action, params)
        res.portal_id = self.portal_id
        res.action_id = command.action_id
        return res
