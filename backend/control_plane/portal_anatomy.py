"""PortalPulse - Portal Anatomy Engine (PRD-03)
Provides dynamic "HOW THIS PORTAL WORKS" architecture DAGs, runtime dependencies,
bottleneck vulnerability analysis, and operational constraints for Nirantar and IEMCRP.
"""

from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class AnatomyNode(BaseModel):
    id: str
    label: str
    type: str  # gateway, service, database, cache, queue, external
    description: str
    technology: str
    status: str = "HEALTHY"  # HEALTHY, DEGRADED, SATURATED, CRITICAL
    metrics: Dict[str, Any] = Field(default_factory=dict)
    capacity_limit: Optional[str] = None
    bottleneck_risk: str = "LOW"  # LOW, MEDIUM, HIGH, SEVERE


class AnatomyEdge(BaseModel):
    source: str
    target: str
    protocol: str  # HTTP/REST, gRPC, TCP/SQL, Redis Protocol
    traffic_weight: float = 1.0
    is_bottleneck: bool = False
    notes: Optional[str] = None


class PortalAnatomy(BaseModel):
    portal_id: str
    portal_name: str
    architecture_type: str  # MICROSERVICES vs MONOLITHIC
    summary: str
    concurrency_model: str
    storage_model: str
    known_bottlenecks: List[str]
    mitigation_strategies: List[str]
    nodes: List[AnatomyNode]
    edges: List[AnatomyEdge]


def get_nirantar_anatomy() -> PortalAnatomy:
    """Returns the architectural DAG and component specs for Nirantar (Modern Microservices)."""
    return PortalAnatomy(
        portal_id="nirantar",
        portal_name="Nirantar Railway & National Examination Portal",
        architecture_type="MICROSERVICES",
        summary="Distributed microservices architecture with decoupled exam delivery, distributed Redis caching, and horizontal autoscaling capabilities.",
        concurrency_model="Asynchronous event-driven worker pools with dynamic horizontal replica autoscaling (Kubernetes / Process).",
        storage_model="Polyglot persistence: Redis in-memory cache cluster fronting PostgreSQL partitioned database with read-replicas.",
        known_bottlenecks=[
            "Worker CPU saturation under high cryptographic verification load",
            "Autoscaler reaction lag (cold container startup latency 15-45s)",
            "Redis eviction churn during cache miss storm"
        ],
        mitigation_strategies=[
            "Token Bucket Waiting Room (Gated Admission with pp_admitted cookie)",
            "Horizontal Pod/Worker Scaling (+2 to +8 replicas)",
            "Aggressive Static Caching & Read Divert",
            "Queue Load Shedding (Dropping non-critical audit events)"
        ],
        nodes=[
            AnatomyNode(
                id="ingress",
                label="API Gateway / Ingress",
                type="gateway",
                description="L7 Envoy Reverse Proxy & Token Bucket Traffic Shaper",
                technology="Envoy / Traefik",
                capacity_limit="10,000 RPS",
                bottleneck_risk="LOW",
                metrics={"active_conns": 340, "ssl_handshakes_sec": 48}
            ),
            AnatomyNode(
                id="auth_service",
                label="Identity & Token Service",
                type="service",
                description="OAuth2/JWT Verification and Session Admission",
                technology="Go / FastAPI Microservice",
                capacity_limit="1,500 RPS",
                bottleneck_risk="MEDIUM",
                metrics={"jwt_verify_latency_ms": 4.2}
            ),
            AnatomyNode(
                id="exam_engine",
                label="Exam Engine Service",
                type="service",
                description="Question delivery, state management, and real-time autosave processor",
                technology="FastAPI Asynchronous Workers",
                capacity_limit="600 RPS per replica",
                bottleneck_risk="HIGH",
                metrics={"replicas": 3, "worker_cpu_pct": 52.0}
            ),
            AnatomyNode(
                id="redis_cluster",
                label="Distributed Cache Cluster",
                type="cache",
                description="High-throughput session and question bank cache (LRU, TTL 180s)",
                technology="Redis 7.2 Cluster",
                capacity_limit="50,000 ops/sec",
                bottleneck_risk="LOW",
                metrics={"hit_rate_pct": 98.4, "memory_used_mb": 240}
            ),
            AnatomyNode(
                id="exam_db",
                label="Exam Database (PostgreSQL)",
                type="database",
                description="Partitioned relational persistence with read-replica pool",
                technology="PostgreSQL 16 (Connection Pool = 200)",
                capacity_limit="1,200 concurrent queries",
                bottleneck_risk="MEDIUM",
                metrics={"active_queries": 28, "replication_lag_ms": 1.2}
            ),
            AnatomyNode(
                id="submission_queue",
                label="Submission Event Stream",
                type="queue",
                description="Durable Kafka/RabbitMQ queue for decoupled asynchronous submission processing",
                technology="RabbitMQ Stream Engine",
                capacity_limit="5,000 msgs/sec",
                bottleneck_risk="LOW",
                metrics={"queue_depth": 14}
            )
        ],
        edges=[
            AnatomyEdge(source="ingress", target="auth_service", protocol="HTTP/2 REST", traffic_weight=0.25),
            AnatomyEdge(source="ingress", target="exam_engine", protocol="HTTP/2 REST", traffic_weight=0.75),
            AnatomyEdge(source="exam_engine", target="redis_cluster", protocol="Redis Protocol (TCP)", traffic_weight=0.65),
            AnatomyEdge(source="exam_engine", target="exam_db", protocol="PostgreSQL Wire", traffic_weight=0.20),
            AnatomyEdge(source="exam_engine", target="submission_queue", protocol="AMQP 0-9-1", traffic_weight=0.15)
        ]
    )


def get_iemcrp_anatomy() -> PortalAnatomy:
    """Returns the architectural DAG and component specs for IEMCRP (Monolithic ERP with Real Constrained DB)."""
    return PortalAnatomy(
        portal_id="iemcrp",
        portal_name="IEMCRP State University Examination Cell",
        architecture_type="MONOLITHIC",
        summary="Traditional monolithic enterprise application server backed by a single relational database with an intentionally constrained connection pool (N=50).",
        concurrency_model="Synchronous multi-threaded WSGI workers constrained by database connection semaphore starvation.",
        storage_model="Single monolithic relational database with strictly constrained connection pool (N=50) and table-level locks on academic results.",
        known_bottlenecks=[
            "Database connection pool exhaustion at N >= 45 concurrent queries",
            "Table lock contention during concurrent faculty grade entry vs student result rushes",
            "Lack of distributed caching forcing heavy joins for marksheets and student dashboards"
        ],
        mitigation_strategies=[
            "Token Bucket Waiting Room (Immediate shedding of queue overflow)",
            "Static Fallback Page Divert (Serving pre-rendered marksheets to spare DB pool)",
            "Connection Pool Expansion (Emergency semaphore increase to 75 slots)",
            "Result Query Rate Limiting (1 req/10s per student session)"
        ],
        nodes=[
            AnatomyNode(
                id="reverse_proxy",
                label="Nginx Reverse Proxy",
                type="gateway",
                description="Frontend SSL termination and static asset server",
                technology="Nginx 1.24",
                capacity_limit="2,500 RPS",
                bottleneck_risk="LOW",
                metrics={"active_client_conns": 180}
            ),
            AnatomyNode(
                id="monolith_app",
                label="Monolithic Web App Server",
                type="service",
                description="Single unified application handling auth, student portal, faculty grading, and reports",
                technology="FastAPI / PHP Monolith WSGI (8 worker threads)",
                capacity_limit="80 concurrent thread workers",
                bottleneck_risk="HIGH",
                metrics={"active_threads": 42, "thread_wait_time_ms": 22.4}
            ),
            AnatomyNode(
                id="local_memory_cache",
                label="Local In-Memory Cache",
                type="cache",
                description="Process-local dictionary cache (volatile, no cross-process synchronization)",
                technology="In-Memory LRU (5,000 keys)",
                capacity_limit="5,000 keys",
                bottleneck_risk="MEDIUM",
                metrics={"hit_rate_pct": 62.1, "evictions_total": 450}
            ),
            AnatomyNode(
                id="monolith_db",
                label="Monolithic Database (MySQL/SQLite)",
                type="database",
                description="Real monolithic relational database with intentionally constrained connection pool",
                technology="Relational DB Pool (STRICT LIMIT = 50 connections)",
                capacity_limit="50 ACTIVE CONNECTIONS",
                bottleneck_risk="SEVERE",
                metrics={"max_pool_size": 50, "active_conns": 46, "waiting_conns": 12, "queue_timeout_ms": 1500}
            )
        ],
        edges=[
            AnatomyEdge(source="reverse_proxy", target="monolith_app", protocol="HTTP/1.1", traffic_weight=1.0),
            AnatomyEdge(source="monolith_app", target="local_memory_cache", protocol="Process Memory Call", traffic_weight=0.40),
            AnatomyEdge(
                source="monolith_app",
                target="monolith_db",
                protocol="Database Connection Pool",
                traffic_weight=0.60,
                is_bottleneck=True,
                notes="CRITICAL CHOKEPOINT: Max 50 connections. Queue starvation triggers 504 Gateway Timeout when concurrency > 50."
            )
        ]
    )


def get_portal_anatomy(portal_id: str) -> PortalAnatomy:
    """Retrieve anatomy by portal ID (defaulting to Nirantar or IEMCRP)."""
    pid = portal_id.lower().replace("-", "_")
    if "college" in pid or "iemcrp" in pid:
        return get_iemcrp_anatomy()
    return get_nirantar_anatomy()
