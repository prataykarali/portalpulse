# PortalPulse Pluggable Connector Architecture & Universal Control Plane

## Executive Architecture Summary
PortalPulse is an **independent, portal-agnostic AIOps and Autonomous SRE Control Plane**. Rather than attempting to inspect random external websites or hardcode site-specific application logic, PortalPulse establishes a **Universal Connector Protocol**. 

Each host portal embeds or runs a lightweight **PortalPulse Connector Agent**. The connector:
1. **Converts host metrics** into the standardized 15-signal Universal Telemetry format.
2. **Discovers & declares infrastructure capabilities** (e.g. horizontal scaling, caching, replicas, rate limiting, queues).
3. **Discovers & declares service topologies** (nodes and dependency edges for dynamic NetworkX causal DAGs).
4. **Enforces Action Masking**: Guarantees the AI policy network never dispatches operations unsupported by the host.
5. **Executes validated mitigation actions** via local handlers or webhook adapters.

---

## 1. Universal Control Plane Topology

```
                    PORTALPULSE CONTROL PLANE
              ┌─────────────────────────────────────┐
              │ M1: Universal Telemetry Ingestion   │
              │ M2: Multi-Horizon Load Forecaster   │
              │ M3: Isolation Forest Anomaly Engine │
              │ M4: Dynamic Causal DAG Root Cause   │
              │ M5: Deep MLP Policy (RTX 2050 CUDA) │
              │ M6: Deterministic Action Masking    │
              │ M7: Closed-Loop Actuation Trajectory│
              └──────────────────┬──────────────────┘
                                 │
                   Universal Connector Protocol
                   (HTTP / gRPC / Embedded SDK)
                                 │
        ┌────────────────────────┼────────────────────────┐
        ↓                        ↓                        ↓
   Nirantar                 State College              eCommerce
   Connector                Portal Connector           Connector
   (Railway ERP)            (Constrained Monolith)     (Microservices)
```

---

## 2. Universal Connector Interface (`BasePortalConnector`)

Located in [`portalpulse_sdk/interface.py`](file:///home/pratay-karali/Desktop/portalpulse/portalpulse_sdk/interface.py):

```python
class BasePortalConnector(ABC):
    @abstractmethod
    def get_telemetry(self) -> UniversalTelemetry:
        """Stream standardized 15-signal telemetry."""

    @abstractmethod
    def get_capabilities(self) -> PortalCapabilities:
        """Declare infrastructure actions supported by the host."""

    @abstractmethod
    def get_dependencies(self) -> DependencyGraphSpec:
        """Expose architectural service graph."""

    @abstractmethod
    def get_health(self) -> Dict[str, Any]:
        """Local health check report."""

    @abstractmethod
    def execute_action(self, command: ActionCommand) -> ActionResult:
        """Execute a validated SRE mitigation action."""
```

---

## 3. Standardized Universal Telemetry Schema

Located in [`portalpulse_sdk/schema.py`](file:///home/pratay-karali/Desktop/portalpulse/portalpulse_sdk/schema.py):

```json
{
  "portal_id": "nirantar",
  "timestamp": "2026-09-04T18:50:00Z",
  "active_users": 34100,
  "requests_per_sec": 4850.0,
  "cpu_percent": 74.5,
  "ram_percent": 71.0,
  "latency_ms": 310.0,
  "throughput": 4820.0,
  "error_rate": 0.003,
  "http_5xx": 2.0,
  "db_latency_ms": 32.0,
  "db_connections": 58.0,
  "queue_length": 25,
  "service_instances": 8,
  "network_in_mb": 42.0,
  "network_out_mb": 95.0,
  "tags": {"env": "production", "region": "ap-south-1"}
}
```

The underlying ML models (XGBoost, Isolation Forest, PyTorch Deep MLP) consume these standardized numerical signals without needing to understand the portal's business logic.

---

## 4. Capability Discovery & Action Masking

Located in [`backend/control_plane/action_masker.py`](file:///home/pratay-karali/Desktop/portalpulse/backend/control_plane/action_masker.py):

When a portal registers, it declares its **infrastructure capabilities**:
```python
class PortalCapabilities(BaseModel):
    horizontal_scaling: bool = True
    caching: bool = True
    database_replica: bool = False   # e.g., Monolithic MySQL
    rate_limiting: bool = True
    request_queue: bool = True
    circuit_breaker: bool = True
    static_fallback: bool = True
    waiting_room: bool = True
```

### The Action Masking Mechanism
When the PyTorch Deep MLP outputs raw softmax probabilities across the 11 discrete SRE actions:
$$\mathbf{P}_{\text{raw}} = [p_0, p_1, \dots, p_{10}]$$

The control plane applies the portal's boolean capability mask $\mathbf{M} \in \{0, 1\}^{11}$:
$$p_{\text{masked}, i} = p_{\text{raw}, i} \cdot M_i$$

The remaining probabilities are re-normalized across permitted actions:
$$p_{\text{effective}, i} = \frac{p_{\text{masked}, i}}{\sum_j p_{\text{masked}, j}}$$

**Example**: On `CollegePortalConnector` (`database_replica=False`, `caching=False`):
- `DIVERT_READS_TO_REPLICA` $\to$ **Masked Out ($0.0$)**
- `PURGE_REDIS_CACHE` $\to$ **Masked Out ($0.0$)**
- Diverted automatically to highest permitted action (e.g. `ENABLE_WAITING_ROOM` or `SCALE_OUT_WORKERS`).

---

## 5. Dynamic Dependency Graph (Dynamic NetworkX DAG)

Located in [`backend/control_plane/dynamic_graph.py`](file:///home/pratay-karali/Desktop/portalpulse/backend/control_plane/dynamic_graph.py):

Rather than hardcoding a static 6-tier architecture, each portal connector declares its own topology:
```json
{
  "nodes": ["student_client", "cloudflare_edge", "php_app_server", "mysql_monolith"],
  "edges": [
    ["student_client", "cloudflare_edge"],
    ["cloudflare_edge", "php_app_server"],
    ["php_app_server", "mysql_monolith"]
  ],
  "entrypoint_node": "student_client"
}
```
PortalPulse dynamically constructs a `networkx.DiGraph`, calculates topological depths from the entrypoint, and traces anomalies from downstream dependencies up to the client.

---

## 6. Embedded Python SDK (`portalpulse_sdk`)

Located in [`portalpulse_sdk/`](file:///home/pratay-karali/Desktop/portalpulse/portalpulse_sdk/):

Developers can plug any Python application into PortalPulse in a few lines of code:

```python
from portalpulse_sdk import PortalPulseAgent, PortalCapabilities

# 1. Initialize agent
agent = PortalPulseAgent(
    portal_id="my_app",
    portal_name="Custom Web Portal",
    capabilities=PortalCapabilities(
        horizontal_scaling=True,
        database_replica=False,
        rate_limiting=True,
    )
)

# 2. Register local mitigation action handlers
@agent.register_action_handler("SCALE_OUT_WORKERS")
def handle_scale(params):
    delta = params.get("delta_instances", 2)
    # Call internal Kubernetes client / AWS ECS / Docker swarm API
    return ActionResult(action_id="act-1", portal_id="my_app", success=True, message="Scaled pods")

# 3. Stream telemetry
tel = agent.build_telemetry(
    active_users=1420,
    requests_per_sec=280.0,
    cpu_percent=68.0,
    ram_percent=62.0,
    latency_ms=210.0,
    throughput=278.0,
    error_rate=0.002,
)
```

---

## 7. Multi-Portal Control Plane API Catalog

| HTTP Method | Route | Description |
|---|---|---|
| `POST` | `/api/v1/portals/register` | Register portal, discover capabilities, compute action mask |
| `GET` | `/api/v1/portals` | List all connected portals and live health status |
| `GET` | `/api/v1/portals/{portal_id}` | Retrieve portal metadata and latest observation |
| `GET` | `/api/v1/portals/{portal_id}/capabilities` | Capability Discovery: inspect permitted infrastructure actions |
| `GET` | `/api/v1/portals/{portal_id}/dependencies` | Dependency Discovery: inspect dynamic topological service graph |
| `POST` | `/api/v1/portals/{portal_id}/telemetry` | Ingest universal telemetry into per-portal ring buffer |
| `GET` | `/api/v1/portals/{portal_id}/telemetry/live` | Fetch latest real-time telemetry observation |
| `POST` | `/api/v1/portals/{portal_id}/actions/prescribe-and-mask` | Run M5 neural policy and apply capability mask |
| `POST` | `/api/v1/portals/{portal_id}/actions/dispatch` | Dispatch approved SRE action to target portal connector |
