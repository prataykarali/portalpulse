"""Universal schemas for the PortalPulse Connector Protocol & SDK.

Standardizes telemetry, infrastructure capabilities, dependency graphs,
and actuation results across heterogeneous host web portals.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field


class ResourceProfile(BaseModel):
    """Discovered physical host, container, and architectural resource envelope of a portal.
    
    Contains pure discovery and configured allocation boundaries.
    Does NOT contain performance-test results (see CapacityProfile).
    """

    portal_id: str = Field(..., description="Unique portal identifier")
    discovered_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 discovery timestamp",
    )
    # Compute Envelope
    host_cpu_cores: int = Field(..., ge=1, description="Host physical/logical CPU execution cores")
    cpu_cores_physical: Optional[int] = Field(default=None, description="Physical CPU cores")
    effective_cpu_limit: Optional[float] = Field(
        default=None, description="Container/cgroup quota limit in cores if constrained"
    )
    # Memory Envelope (MB)
    host_ram_mb: float = Field(..., ge=0.0, description="Total host RAM in megabytes")
    effective_ram_limit_mb: Optional[float] = Field(
        default=None, description="Effective container/cgroup RAM limit in megabytes"
    )
    # Storage & Filesystem
    disk_total_gb: float = Field(default=100.0, ge=0.0, description="Filesystem volume capacity in GB")
    disk_free_gb: float = Field(default=50.0, ge=0.0, description="Free filesystem storage in GB")
    # Network Envelope
    network_bandwidth_mbps: Optional[float] = Field(
        default=None, description="Network interface bandwidth cap in Mbps"
    )
    # Architectural Allocations
    worker_count: int = Field(default=1, ge=1, description="Number of application worker processes")
    worker_concurrency: int = Field(
        default=32, ge=1, description="Max concurrent request threads/coroutines per worker"
    )
    db_pool_size: Optional[int] = Field(
        default=None, ge=1, description="Configured database connection pool size"
    )
    db_connection_limit: Optional[int] = Field(
        default=None, ge=1, description="Database server maximum connection limit"
    )
    service_instances: int = Field(default=1, ge=1, description="Active running application instances/pods")
    max_service_instances: int = Field(default=32, ge=1, description="Maximum allowable scaling replica ceiling")
    cgroup_version: Optional[str] = Field(default=None, description="Detected cgroup version ('v1', 'v2', or 'none')")


class CapacityProfile(BaseModel):
    """Observed capacity boundaries measured exclusively during controlled capacity benchmark tests.
    
    Represents empirical performance limits rather than static hardware discovery.
    """

    portal_id: str = Field(..., description="Unique portal identifier")
    measured_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 benchmark timestamp",
    )
    sustainable_rps: float = Field(..., ge=0.0, description="Maximum arrival rate sustained under SLA (<100ms P95)")
    saturation_rps: float = Field(..., ge=0.0, description="Arrival rate where throughput plateaus and errors spike")
    sustainable_active_sessions: int = Field(
        ..., ge=0, description="Maximum concurrent active human sessions sustained within SLA"
    )
    degradation_knee_rps: float = Field(
        ..., ge=0.0, description="Arrival throughput at the knee of the latency curve"
    )
    degradation_knee_vus: int = Field(
        ..., ge=0, description="Simulated virtual user population at the degradation knee-point"
    )
    limiting_bottleneck: str = Field(
        ..., description="Primary constrained tier (e.g. 'WORKER_CPU', 'DB_POOL_EXHAUSTION', 'EVENT_LOOP_DELAY')"
    )
    p95_at_knee_ms: float = Field(default=50.0, ge=0.0, description="P95 response latency observed at degradation knee")
    error_rate_at_saturation: float = Field(default=0.05, ge=0.0, description="Error rate observed at saturation point")


class UniversalTelemetry(BaseModel):
    """Standardized multi-signal telemetry schema accepted by PortalPulse from any connector.

    Converts disparate portal infrastructure signals into a uniform, ML-digestible telemetry representation.
    """

    portal_id: str = Field(..., description="Unique identifier of the reporting portal (e.g. 'nirantar')")
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 UTC timestamp",
    )
    active_users: int = Field(..., ge=0, description="Concurrent active users/sessions (legacy backward-compatible)")
    requests_per_sec: float = Field(..., ge=0.0, description="HTTP arrival throughput in requests/sec")
    cpu_percent: float = Field(..., ge=0.0, le=100.0, description="Mean host/container CPU utilization (%)")
    ram_percent: float = Field(..., ge=0.0, le=100.0, description="Mean host/container RAM utilization (%)")
    latency_ms: float = Field(..., ge=0.0, description="Mean round-trip request latency (ms)")
    throughput: float = Field(..., ge=0.0, description="Successfully delivered responses/sec")
    error_rate: float = Field(..., ge=0.0, le=1.0, description="Fraction of failed requests (4xx/5xx)")
    http_5xx: float = Field(default=0.0, ge=0.0, description="Rate of 5xx server errors per second")
    db_latency_ms: float = Field(default=0.0, ge=0.0, description="Mean database query latency (ms)")
    db_connections: float = Field(
        default=0.0, ge=0.0, le=100.0, description="Database connection pool saturation (%)"
    )
    queue_length: int = Field(default=0, ge=0, description="Backlog in ingress queue / waiting room")
    service_instances: int = Field(default=4, ge=1, description="Active worker replica count / pod count")
    network_in_mb: float = Field(default=10.0, ge=0.0, description="Inbound network traffic (MB/s)")
    network_out_mb: float = Field(default=25.0, ge=0.0, description="Outbound network traffic (MB/s)")
    tags: Dict[str, str] = Field(default_factory=dict, description="Custom metadata tags (e.g. region, env)")

    # Nullable extended metrics (strictly None when not actively instrumented/available)
    active_sessions: Optional[int] = Field(
        default=None, description="Distinct human/client sessions active within last 30s sliding window"
    )
    concurrent_requests: Optional[int] = Field(
        default=None, description="HTTP transactions currently in-flight on the server"
    )
    p50_latency_ms: Optional[float] = Field(default=None, description="50th percentile latency (ms)")
    p95_latency_ms: Optional[float] = Field(default=None, description="95th percentile latency (ms)")
    p99_latency_ms: Optional[float] = Field(default=None, description="99th percentile latency (ms)")
    memory_used_mb: Optional[float] = Field(default=None, description="Memory used in megabytes")
    memory_limit_mb: Optional[float] = Field(default=None, description="Memory limit in megabytes")
    cpu_cores: Optional[int] = Field(default=None, description="Effective CPU cores available to worker")
    db_connection_limit: Optional[int] = Field(default=None, description="Configured DB connection pool limit")
    http_4xx: Optional[float] = Field(default=None, description="Rate of 4xx client errors per second")


class PortalCapabilities(BaseModel):
    """Infrastructure capabilities declared by a host portal connector.

    PortalPulse uses this capability contract to construct an Action Mask, preventing
    ML policy networks from attempting operations not supported by the portal.
    """

    horizontal_scaling: bool = Field(
        default=True, description="Can scale application pods/workers horizontally"
    )
    vertical_scaling: bool = Field(
        default=False, description="Can dynamically adjust CPU/RAM resource limits"
    )
    caching: bool = Field(
        default=True, description="Supports Redis/Memcached cache purge or TTL tuning"
    )
    static_fallback: bool = Field(
        default=True, description="Can serve static cached CDN landing page on critical outage"
    )
    rate_limiting: bool = Field(
        default=True, description="Supports edge token bucket rate limiting"
    )
    request_queue: bool = Field(
        default=True, description="Can throttle and drain ingress requests in a queue"
    )
    database_replica: bool = Field(
        default=False, description="Has read replica pool capable of handling diverted reads"
    )
    database_pool_scaling: bool = Field(
        default=True, description="Can dynamically expand DB connection pool limits"
    )
    circuit_breaker: bool = Field(
        default=True, description="Supports circuit breaker tripping and fallback routing"
    )
    pod_restart: bool = Field(
        default=True, description="Supports restarting hung or degraded worker pods"
    )
    waiting_room: bool = Field(
        default=True, description="Supports virtual waiting room queue during flash surges"
    )
    feature_flags: bool = Field(
        default=False, description="Supports disabling non-essential features under high load"
    )
    min_instances: int = Field(default=2, ge=1, description="Minimum allowable service replicas")
    max_instances: int = Field(default=20, ge=1, description="Maximum allowable service replicas")


class DependencyGraphSpec(BaseModel):
    """Declarative architectural topology exposed by the connector.

    Allows PortalPulse's NetworkX causal DAG to be generated dynamically
    per portal rather than hardcoded to a single static architecture.
    """

    nodes: List[str] = Field(
        default_factory=lambda: [
            "client",
            "cdn_edge",
            "api_gateway",
            "worker_backend",
            "postgresql_db",
            "redis_cache",
        ],
        description="Physical and logical service nodes in the portal topology",
    )
    edges: List[Tuple[str, str]] = Field(
        default_factory=lambda: [
            ("client", "cdn_edge"),
            ("cdn_edge", "api_gateway"),
            ("api_gateway", "worker_backend"),
            ("worker_backend", "postgresql_db"),
            ("worker_backend", "redis_cache"),
        ],
        description="Directed causal dependencies (source -> target dependency)",
    )
    entrypoint_node: str = Field(default="client", description="Root user ingress node")
    storage_nodes: List[str] = Field(
        default_factory=lambda: ["postgresql_db", "redis_cache"],
        description="Downstream persistence or cache tiers",
    )


class ActionCommand(BaseModel):
    """Standardized action command dispatched from PortalPulse to a portal connector."""

    action_id: str = Field(..., description="Unique action tracking ID")
    portal_id: str = Field(..., description="Target portal identifier")
    action_type: str = Field(..., description="Action name, matching SREAction enum")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Action specific execution parameters")
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 UTC dispatch timestamp",
    )


class ActionResult(BaseModel):
    """Outcome reported back by the connector after executing an action."""

    action_id: str = Field(..., description="Matched action tracking ID")
    portal_id: str = Field(default="default", description="Target portal identifier")
    success: bool = Field(default=True, description="Whether execution completed cleanly on the host")
    message: str = Field(default="Action execution completed", description="Execution outcome or error summary")
    status: str = Field(default="SUCCESS", description="Execution outcome status string")
    command: Optional[str] = Field(default=None, description="Executed action command")
    execution_time_ms: Optional[float] = Field(default=None, description="Execution duration in milliseconds")
    rollback_available: bool = Field(default=False, description="Whether automated rollback is available")
    rollback_command: Optional[str] = Field(default=None, description="Automated rollback command")
    rollback_parameters: Optional[Dict[str, Any]] = Field(default=None, description="Rollback parameter payload")
    executed_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 execution timestamp",
    )
    observed_delta: Dict[str, float] = Field(
        default_factory=dict, description="Immediate metrics change observed by host agent"
    )
