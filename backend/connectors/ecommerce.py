"""Reference Connector for Microservices eCommerce Store.

Demonstrates capability discovery for a microservices store featuring
feature flag degradation, dynamic rate limiting, and circuit breaking.
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


class ECommerceConnector(BasePortalConnector):
    """Connector for an eCommerce retail portal."""

    def __init__(self) -> None:
        super().__init__(portal_id="ecommerce", portal_name="Global Retail Flash Deal Store")
        self.pods: int = 6
        self.recommendations_disabled: bool = False
        self.circuit_open: bool = False
        self.simulation_mode: bool = False
        self._latest_capacity_profile: Optional[CapacityProfile] = None

    def get_resources(self) -> ResourceProfile:
        """Discover ECommerce platform's real host hardware and microservices limits."""
        return discover_resource_envelope(
            portal_id=self.portal_id,
            worker_count=self.pods,
            worker_concurrency=32,
            db_pool_size=80,
            db_connection_limit=120,
            service_instances=self.pods,
            max_service_instances=24,
        )

    def get_capacity_profile(self) -> Optional[CapacityProfile]:
        return self._latest_capacity_profile

    def set_capacity_profile(self, profile: CapacityProfile) -> None:
        self._latest_capacity_profile = profile

    def get_capabilities(self) -> PortalCapabilities:
        """Modern cloud-native microservices architecture on Kubernetes."""
        return PortalCapabilities(
            horizontal_scaling=True,
            vertical_scaling=False,
            caching=True,
            static_fallback=True,
            rate_limiting=True,
            request_queue=True,
            database_replica=True,
            database_pool_scaling=False,
            circuit_breaker=True,
            pod_restart=True,
            waiting_room=True,
            feature_flags=True,  # Supports dynamic feature degradation
            min_instances=3,
            max_instances=24,
        )

    def get_dependencies(self) -> DependencyGraphSpec:
        """5-node DAG microservices topology."""
        return DependencyGraphSpec(
            nodes=[
                "shopper_app",
                "envoy_gateway",
                "checkout_service",
                "payment_gateway",
                "aurora_db_cluster",
            ],
            edges=[
                ("shopper_app", "envoy_gateway"),
                ("envoy_gateway", "checkout_service"),
                ("checkout_service", "payment_gateway"),
                ("checkout_service", "aurora_db_cluster"),
            ],
            entrypoint_node="shopper_app",
            storage_nodes=["aurora_db_cluster"],
        )

    def get_health(self) -> Dict[str, Any]:
        """Local health check report."""
        return {
            "status": "HEALTHY",
            "pods": self.pods,
            "feature_flags_active": self.recommendations_disabled,
            "circuit_open": self.circuit_open,
            "simulation_mode": self.simulation_mode,
        }

    def get_telemetry(self) -> UniversalTelemetry:
        """Generate telemetry for eCommerce platform.
        Defaults to real idle baseline numbers when no flash sale load test is active.
        """
        if not self.simulation_mode:
            # REAL FOUND NUMBERS (Idle baseline: 0 shoppers, nominal storefront)
            return UniversalTelemetry(
                portal_id=self.portal_id,
                timestamp=datetime.now(timezone.utc).isoformat(),
                active_users=0,
                requests_per_sec=round(random.uniform(0.1, 0.25), 2),
                cpu_percent=round(random.uniform(2.1, 3.8), 1),
                ram_percent=round(random.uniform(15.0, 19.5), 1),
                latency_ms=round(random.uniform(1.1, 2.2), 1),
                throughput=round(random.uniform(0.1, 0.25), 2),
                error_rate=0.0,
                http_5xx=0.0,
                db_latency_ms=round(random.uniform(0.5, 1.2), 1),
                db_connections=2.0,
                queue_length=0,
                service_instances=self.pods,
                network_in_mb=0.1,
                network_out_mb=0.15,
                tags={"env": "local_production", "mode": "real_baseline", "tier": "retail"},
                active_sessions=0,
                concurrent_requests=0,
                p50_latency_ms=round(random.uniform(1.2, 2.0), 1),
                p95_latency_ms=round(random.uniform(2.2, 3.5), 1),
                p99_latency_ms=round(random.uniform(3.5, 5.2), 1),
                memory_used_mb=420.0,
                memory_limit_mb=3072.0,
                cpu_cores=6,
                db_connection_limit=120,
                http_4xx=0.0,
            )

        # SIMULATION / BENCHMARK STRESS TEST (Simulated Flash Sale Rush)
        # Distinct: Active Sessions (21,500) vs RPS (2,650) vs In-Flight Requests (180)
        return UniversalTelemetry(
            portal_id=self.portal_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            active_users=21500,
            requests_per_sec=2650.0,
            cpu_percent=round(random.uniform(55.0, 72.0), 1),
            ram_percent=round(random.uniform(60.0, 68.0), 1),
            latency_ms=210.0,
            throughput=2610.0,
            error_rate=0.003,
            http_5xx=1.0,
            db_latency_ms=16.0,
            db_connections=48.0,
            queue_length=12,
            service_instances=self.pods,
            network_in_mb=28.0,
            network_out_mb=78.0,
            tags={"env": "simulation", "org": "retail_corp", "tier": "flash_sale"},
            active_sessions=21500,
            concurrent_requests=180,
            p50_latency_ms=145.0,
            p95_latency_ms=290.0,
            p99_latency_ms=440.0,
            memory_used_mb=2100.0,
            memory_limit_mb=3072.0,
            cpu_cores=6,
            db_connection_limit=120,
            http_4xx=8.0,
        )

    def execute_action(self, command: ActionCommand) -> ActionResult:
        """Execute action on eCommerce platform."""
        action = command.action_type
        params = command.parameters

        if action == "SCALE_OUT_WORKERS":
            added = int(params.get("delta_instances", 2))
            self.pods = min(24, self.pods + added)
            return ActionResult(
                action_id=command.action_id,
                portal_id=self.portal_id,
                success=True,
                message=f"Scaled out checkout microservice to {self.pods} pods.",
                observed_delta={"service_instances": float(self.pods), "cpu_percent_delta": -15.0},
            )
        elif action == "ENGAGE_CIRCUIT_BREAKER":
            self.circuit_open = True
            return ActionResult(
                action_id=command.action_id,
                portal_id=self.portal_id,
                success=True,
                message="Tripped Envoy circuit breaker for slow third-party payment partner.",
                observed_delta={"latency_ms_delta": -120.0},
            )

        return ActionResult(
            action_id=command.action_id,
            portal_id=self.portal_id,
            success=True,
            message=f"Executed action '{action}' on eCommerce store.",
        )
