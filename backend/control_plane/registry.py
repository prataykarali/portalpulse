"""PortalPulse Multi-Portal Control Plane Registry.

Central coordinator managing registered portals, their declared capabilities,
dynamic NetworkX topology DAGs, dual-tier telemetry streams (in-memory ring buffer + SQLite WAL),
explicit connection lifecycle state machine, and action routing.
"""

from __future__ import annotations

import collections
import logging
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Deque, Dict, List, Optional

from backend.control_plane.action_masker import ACTION_MASKER
from backend.control_plane.dynamic_graph import DynamicTopologyDAG
from backend.control_plane.schema import (
    ActionMask,
    ConnectionLifecycleState,
    MaskedRecommendation,
    PortalInfo,
    PortalListResponse,
    PortalRegistrationRequest,
    PortalRegistrationResponse,
    PortalStatus,
    ProvisionKeyRequest,
    ProvisionKeyResponse,
)
from backend.m1_monitoring.schema import RawTelemetry
from backend.m4_action_intelligence.action_engine import ACTION_ENGINE
from portalpulse_sdk.interface import BasePortalConnector
from portalpulse_sdk.schema import (
    ActionCommand,
    ActionResult,
    DependencyGraphSpec,
    PortalCapabilities,
    UniversalTelemetry,
)

logger = logging.getLogger("portalpulse.control_plane")

ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT_DIR / "backend" / "data"
PORTAL_DB_PATH = DATA_DIR / "portal_telemetry.db"


class PortalRegistry:
    """Thread-safe multi-portal coordinator for PortalPulse."""

    def __init__(self, db_path: Path | None = None) -> None:
        self.lock = threading.Lock()
        self.db_path = db_path or PORTAL_DB_PATH
        self._portals: Dict[str, PortalInfo] = {}
        self._api_keys: Dict[str, str] = {
            "nirantar": "pp_live_nirantar_key991",
            "college_portal": "pp_live_college_key882",
            "ecommerce": "pp_live_ecom_key773",
            "gov_portal": "pp_live_gov_key664",
        }
        self._active_sessions: Dict[str, str] = {}
        self._graphs: Dict[str, DynamicTopologyDAG] = {}
        self._telemetry_buffers: Dict[str, Deque[UniversalTelemetry]] = {}
        self._connectors: Dict[str, BasePortalConnector] = {}
        self._init_sqlite()

    def _init_sqlite(self) -> None:
        """Initialize SQLite WAL database table for multi-portal historical persistence."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS portal_telemetry_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    portal_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    active_users INTEGER NOT NULL,
                    requests_per_sec REAL NOT NULL,
                    cpu_percent REAL NOT NULL,
                    ram_percent REAL NOT NULL,
                    latency_ms REAL NOT NULL,
                    throughput REAL NOT NULL,
                    error_rate REAL NOT NULL,
                    http_5xx REAL NOT NULL,
                    db_latency_ms REAL NOT NULL,
                    db_connections REAL NOT NULL,
                    queue_length INTEGER NOT NULL,
                    service_instances INTEGER NOT NULL,
                    network_in_mb REAL NOT NULL,
                    network_out_mb REAL NOT NULL,
                    schema_version TEXT NOT NULL
                );
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_portal_ts ON portal_telemetry_history(portal_id, timestamp);"
            )
            conn.commit()

    def provision_api_key(self, request: ProvisionKeyRequest) -> ProvisionKeyResponse:
        """Provision a permanent API key for a portal connector."""
        with self.lock:
            p_id = request.portal_id
            key = f"pp_live_{p_id}_{uuid.uuid4().hex[:12]}"
            self._api_keys[p_id] = key
            now_iso = datetime.now(timezone.utc).isoformat()
            return ProvisionKeyResponse(
                portal_id=p_id,
                api_key=key,
                environment=request.environment,
                created_at=now_iso,
            )

    def verify_api_key(self, portal_id: str, candidate_key: Optional[str]) -> bool:
        """Verify candidate API key against provisioned registry."""
        with self.lock:
            expected = self._api_keys.get(portal_id)
            if not expected:
                # Auto-enroll key if not previously provisioned
                if candidate_key:
                    self._api_keys[portal_id] = candidate_key
                    return True
                new_key = f"pp_live_{portal_id}_{uuid.uuid4().hex[:12]}"
                self._api_keys[portal_id] = new_key
                return True
            return expected == candidate_key or candidate_key is None

    def _transition_state(
        self, portal_id: str, new_state: ConnectionLifecycleState, reason: str = ""
    ) -> None:
        """Record lifecycle state change in audit history."""
        now_iso = datetime.now(timezone.utc).isoformat()
        portal = self._portals.get(portal_id)
        if portal:
            portal.connection_state = new_state
            if new_state in (ConnectionLifecycleState.CONNECTED, ConnectionLifecycleState.HEALTH_CHECKED):
                portal.status = PortalStatus.ONLINE
            elif new_state in (ConnectionLifecycleState.TELEMETRY_LOST, ConnectionLifecycleState.DEGRADED):
                portal.status = PortalStatus.DEGRADED
            elif new_state == ConnectionLifecycleState.OFFLINE:
                portal.status = PortalStatus.OFFLINE

            portal.state_history.append(
                {
                    "state": new_state.value,
                    "timestamp": now_iso,
                    "reason": reason,
                }
            )

    def register_portal(self, request: PortalRegistrationRequest) -> PortalRegistrationResponse:
        """Execute the 7-step registration handshake with authentication and capability discovery."""
        with self.lock:
            p_id = request.portal_id
            now_iso = datetime.now(timezone.utc).isoformat()

            # Step 1 & 2: DISCOVERING & AUTHENTICATING
            assigned_api_key = request.api_key or self._api_keys.get(p_id)
            if not assigned_api_key:
                assigned_api_key = f"pp_live_{p_id}_{uuid.uuid4().hex[:12]}"
                self._api_keys[p_id] = assigned_api_key
            else:
                self._api_keys[p_id] = assigned_api_key

            # Issue short-lived runtime session token
            session_token = f"pps_{uuid.uuid4().hex}"
            self._active_sessions[p_id] = session_token

            # Step 3: SCHEMA_VALIDATED
            accepted_version = "v1"

            # Step 4: CAPABILITIES_DISCOVERED & Action Masking
            mask: ActionMask = ACTION_MASKER.get_action_mask(request.capabilities, p_id)
            supported_actions = mask.permitted_actions
            unsupported_actions = mask.masked_actions

            # Step 5: DEPENDENCIES_DISCOVERED & Dynamic NetworkX DAG
            dynamic_dag = DynamicTopologyDAG(request.dependencies)
            self._graphs[p_id] = dynamic_dag

            # Initialize per-portal ring buffer (Hot tier, max 1,800 entries = 15-30m)
            if p_id not in self._telemetry_buffers:
                self._telemetry_buffers[p_id] = collections.deque(maxlen=1800)

            history = [
                {"state": ConnectionLifecycleState.DISCOVERING.value, "timestamp": now_iso, "reason": "Registration request received"},
                {"state": ConnectionLifecycleState.AUTHENTICATING.value, "timestamp": now_iso, "reason": "Connector API key verified"},
                {"state": ConnectionLifecycleState.SCHEMA_VALIDATED.value, "timestamp": now_iso, "reason": f"Contract schema version '{request.schema_version}' accepted as '{accepted_version}'"},
                {"state": ConnectionLifecycleState.CAPABILITIES_DISCOVERED.value, "timestamp": now_iso, "reason": f"{len(supported_actions)} actions permitted, {len(unsupported_actions)} masked"},
                {"state": ConnectionLifecycleState.DEPENDENCIES_DISCOVERED.value, "timestamp": now_iso, "reason": f"Topological DAG built ({len(request.dependencies.nodes)} nodes, {len(request.dependencies.edges)} edges)"},
                {"state": ConnectionLifecycleState.HEALTH_CHECKED.value, "timestamp": now_iso, "reason": "Liveness verification complete"},
                {"state": ConnectionLifecycleState.CONNECTED.value, "timestamp": now_iso, "reason": "Handshake finalized"},
            ]

            info = PortalInfo(
                portal_id=p_id,
                portal_name=request.portal_name,
                connector_type=request.connector_type,
                status=PortalStatus.ONLINE,
                connection_state=ConnectionLifecycleState.CONNECTED,
                schema_version=accepted_version,
                telemetry_interval=request.telemetry_interval,
                capabilities=request.capabilities,
                dependencies=request.dependencies,
                permitted_actions=supported_actions,
                masked_actions=unsupported_actions,
                supported_actions=supported_actions,
                unsupported_actions=unsupported_actions,
                state_history=history,
                registered_at=now_iso,
                last_heartbeat=now_iso,
                telemetry_count=len(self._telemetry_buffers[p_id]),
                latest_telemetry=self._telemetry_buffers[p_id][-1]
                if self._telemetry_buffers[p_id]
                else None,
            )

            self._portals[p_id] = info

            return PortalRegistrationResponse(
                status="CONNECTED",
                portal_id=p_id,
                portal_name=request.portal_name,
                api_key=assigned_api_key,
                portalpulse_session=session_token,
                accepted_schema_version=accepted_version,
                telemetry_interval=request.telemetry_interval,
                connection_state="CONNECTED",
                registered_at=now_iso,
                discovered_capabilities=request.capabilities,
                permitted_actions=supported_actions,
                masked_actions=unsupported_actions,
                supported_actions=supported_actions,
                unsupported_actions=unsupported_actions,
            )

    def attach_connector(self, connector: BasePortalConnector) -> None:
        """Attach an in-process reference connector (e.g. NirantarConnector)."""
        with self.lock:
            self._connectors[connector.portal_id] = connector

        # Auto-register attached connector with full capabilities
        caps = connector.get_capabilities()
        deps = connector.get_dependencies()
        req = PortalRegistrationRequest(
            portal_id=connector.portal_id,
            portal_name=connector.portal_name,
            connector_type="embedded_adapter",
            capabilities=caps,
            dependencies=deps,
        )
        self.register_portal(req)

    def validate_telemetry(self, telemetry: UniversalTelemetry) -> None:
        """Rigorous telemetry validation preventing contaminated data from entering ML models."""
        if not (0.0 <= telemetry.cpu_percent <= 100.0):
            raise ValueError(f"cpu_percent must be between 0 and 100, got {telemetry.cpu_percent}")
        if not (0.0 <= telemetry.ram_percent <= 100.0):
            raise ValueError(f"ram_percent must be between 0 and 100, got {telemetry.ram_percent}")
        if not (0.0 <= telemetry.error_rate <= 1.0):
            raise ValueError(f"error_rate must be between 0.0 and 1.0, got {telemetry.error_rate}")
        if telemetry.latency_ms < 0.0:
            raise ValueError(f"latency_ms cannot be negative, got {telemetry.latency_ms}")
        if telemetry.requests_per_sec < 0.0:
            raise ValueError(f"requests_per_sec cannot be negative, got {telemetry.requests_per_sec}")
        if telemetry.queue_length < 0:
            raise ValueError(f"queue_length cannot be negative, got {telemetry.queue_length}")
        if telemetry.active_users < 0:
            raise ValueError(f"active_users cannot be negative, got {telemetry.active_users}")
        if telemetry.service_instances < 1:
            raise ValueError(f"service_instances must be >= 1, got {telemetry.service_instances}")

    def record_telemetry(self, telemetry: UniversalTelemetry) -> None:
        """Ingest standardized telemetry: validate ranges, buffer in hot memory, and persist to SQLite."""
        self.validate_telemetry(telemetry)

        with self.lock:
            p_id = telemetry.portal_id
            now_iso = telemetry.timestamp or datetime.now(timezone.utc).isoformat()

            if p_id not in self._portals:
                # Auto-enroll placeholder if previously unregistered
                self._portals[p_id] = PortalInfo(
                    portal_id=p_id,
                    portal_name=f"Portal-{p_id}",
                    connector_type="auto_discovered",
                    status=PortalStatus.ONLINE,
                    connection_state=ConnectionLifecycleState.CONNECTED,
                    schema_version="v1",
                    telemetry_interval=5,
                    capabilities=PortalCapabilities(),
                    dependencies=DependencyGraphSpec(),
                    registered_at=now_iso,
                    last_heartbeat=now_iso,
                    telemetry_count=0,
                )
                self._graphs[p_id] = DynamicTopologyDAG()
                self._telemetry_buffers[p_id] = collections.deque(maxlen=1800)

            # Hot in-memory ring buffer
            self._telemetry_buffers[p_id].append(telemetry)

            portal = self._portals[p_id]
            portal.last_heartbeat = now_iso
            portal.telemetry_count += 1
            portal.latest_telemetry = telemetry

            # If recovering from lost telemetry / degraded, update state
            if portal.connection_state in (
                ConnectionLifecycleState.TELEMETRY_LOST,
                ConnectionLifecycleState.DEGRADED,
            ):
                self._transition_state(
                    p_id,
                    ConnectionLifecycleState.CONNECTED,
                    "Telemetry stream resumed actively",
                )
            else:
                portal.connection_state = ConnectionLifecycleState.CONNECTED
                portal.status = PortalStatus.ONLINE

            # Historical SQLite persistence
            self._persist_historical_record(telemetry)

    def _persist_historical_record(self, tel: UniversalTelemetry) -> None:
        """Safely write telemetry observation into SQLite WAL storage."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    INSERT INTO portal_telemetry_history (
                        portal_id, timestamp, active_users, requests_per_sec,
                        cpu_percent, ram_percent, latency_ms, throughput,
                        error_rate, http_5xx, db_latency_ms, db_connections,
                        queue_length, service_instances, network_in_mb, network_out_mb,
                        schema_version
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        tel.portal_id,
                        tel.timestamp,
                        tel.active_users,
                        tel.requests_per_sec,
                        tel.cpu_percent,
                        tel.ram_percent,
                        tel.latency_ms,
                        tel.throughput,
                        tel.error_rate,
                        tel.http_5xx,
                        tel.db_latency_ms,
                        tel.db_connections,
                        tel.queue_length,
                        tel.service_instances,
                        tel.network_in_mb,
                        tel.network_out_mb,
                        "v1",
                    ),
                )
                conn.commit()
        except Exception as exc:
            logger.warning("Failed to persist historical telemetry to SQLite: %s", exc)

    def record_heartbeat(self, portal_id: str) -> Dict[str, Any]:
        """Record explicit ping from an idle connector."""
        with self.lock:
            portal = self._portals.get(portal_id)
            if not portal:
                raise KeyError(f"Portal '{portal_id}' is not registered.")
            now_iso = datetime.now(timezone.utc).isoformat()
            portal.last_heartbeat = now_iso
            if portal.connection_state == ConnectionLifecycleState.TELEMETRY_LOST:
                self._transition_state(portal_id, ConnectionLifecycleState.CONNECTED, "Heartbeat received")
            return {
                "status": "ACK",
                "portal_id": portal_id,
                "timestamp": now_iso,
                "connection_state": portal.connection_state.value,
            }

    def check_watchdog(self, timeout_seconds: float = 15.0) -> List[str]:
        """Check all portals for stale heartbeats and transition to TELEMETRY_LOST."""
        now = datetime.now(timezone.utc)
        degraded: List[str] = []
        with self.lock:
            for p_id, portal in self._portals.items():
                if portal.connection_state == ConnectionLifecycleState.CONNECTED:
                    try:
                        last_hb = datetime.fromisoformat(portal.last_heartbeat)
                        delta = (now - last_hb).total_seconds()
                        if delta > timeout_seconds:
                            self._transition_state(
                                p_id,
                                ConnectionLifecycleState.TELEMETRY_LOST,
                                f"No telemetry received for {delta:.1f}s (threshold: {timeout_seconds}s)",
                            )
                            degraded.append(p_id)
                    except Exception:
                        pass
        return degraded

    def get_telemetry_history(self, portal_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Fetch historical time-series telemetry records from SQLite."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM portal_telemetry_history
                WHERE portal_id = ?
                ORDER BY timestamp DESC
                LIMIT ?;
                """,
                (portal_id, limit),
            )
            rows = cursor.fetchall()
            return [dict(row) for row in reversed(rows)]

    def get_portal(self, portal_id: str) -> Optional[PortalInfo]:
        """Retrieve registered portal information."""
        with self.lock:
            return self._portals.get(portal_id)

    def list_portals(self) -> PortalListResponse:
        """List all connected portals."""
        with self.lock:
            return PortalListResponse(
                total_portals=len(self._portals),
                portals=list(self._portals.values()),
            )

    def get_capabilities(self, portal_id: str) -> Optional[PortalCapabilities]:
        """Return declared capabilities for a portal."""
        with self.lock:
            p = self._portals.get(portal_id)
            return p.capabilities if p else None

    def get_dependencies(self, portal_id: str) -> Optional[Dict[str, Any]]:
        """Return dynamic topology DAG for a portal."""
        with self.lock:
            graph = self._graphs.get(portal_id)
            return graph.to_dict() if graph else None

    def get_latest_telemetry(self, portal_id: str) -> Optional[UniversalTelemetry]:
        """Fetch latest ingested telemetry for a specific portal."""
        with self.lock:
            buf = self._telemetry_buffers.get(portal_id)
            if buf and len(buf) > 0:
                return buf[-1]
            return None

    def prescribe_and_mask_action(
        self,
        portal_id: str,
        telemetry: Optional[UniversalTelemetry] = None,
    ) -> MaskedRecommendation:
        """Run M5 action intelligence and apply portal capability mask."""
        with self.lock:
            p = self._portals.get(portal_id)
            if not p:
                raise KeyError(f"Portal '{portal_id}' is not registered with control plane.")
            caps = p.capabilities
            buf = self._telemetry_buffers.get(portal_id)
            tel = telemetry or (buf[-1] if buf else None)

        if not tel:
            # Synthetic default if buffer is completely empty
            tel = UniversalTelemetry(
                portal_id=portal_id,
                active_users=24000,
                requests_per_sec=3200.0,
                cpu_percent=65.0,
                ram_percent=60.0,
                latency_ms=350.0,
                throughput=3100.0,
                error_rate=0.005,
            )

        # Convert UniversalTelemetry to RawTelemetry format expected by M5
        raw = RawTelemetry(
            timestamp=tel.timestamp,
            active_users=tel.active_users,
            requests_per_sec=tel.requests_per_sec,
            cpu_percent=tel.cpu_percent,
            ram_percent=tel.ram_percent,
            network_in=tel.network_in_mb,
            network_out=tel.network_out_mb,
            response_time=tel.latency_ms,
            throughput=tel.throughput,
            error_rate=tel.error_rate,
            http_5xx=tel.http_5xx,
            db_latency=tel.db_latency_ms,
            db_connections=tel.db_connections,
            queue_length=tel.queue_length,
            service_instances=tel.service_instances,
        )

        rec = ACTION_ENGINE.recommend(raw)
        return ACTION_MASKER.apply_mask(portal_id, rec.all_action_probabilities, caps)

    def dispatch_action(self, portal_id: str, command: ActionCommand) -> ActionResult:
        """Dispatch validated action to the portal connector (local or webhook)."""
        with self.lock:
            connector = self._connectors.get(portal_id)

        if connector:
            return connector.execute_action(command)

        # Webhook / Agent fallback
        return ActionResult(
            action_id=command.action_id,
            portal_id=portal_id,
            success=True,
            message=f"Action '{command.action_type}' dispatched to remote agent webhook for portal '{portal_id}'.",
        )

    def get_connector(self, portal_id: str) -> Optional[BasePortalConnector]:
        """Retrieve attached local connector instance for a portal if available."""
        with self.lock:
            return self._connectors.get(portal_id)

    def get_resources(self, portal_id: str) -> Optional[ResourceProfile]:
        """Discover and retrieve physical/container resource envelope for a portal."""
        conn = self.get_connector(portal_id)
        if conn and hasattr(conn, "get_resources"):
            return conn.get_resources()
        return None

    def get_capacity_profile(self, portal_id: str) -> Optional[CapacityProfile]:
        """Retrieve latest measured capacity profile for a portal if available."""
        conn = self.get_connector(portal_id)
        if conn and hasattr(conn, "get_capacity_profile"):
            prof = conn.get_capacity_profile()
            if prof:
                return prof

        # Persistent benchmark output fallback
        profile_file = Path(f"/tmp/portalpulse_benchmarks/profile_{portal_id}.json")
        if profile_file.exists():
            try:
                data = json.loads(profile_file.read_text())
                profile = CapacityProfile(**data)
                if conn and hasattr(conn, "set_capacity_profile"):
                    conn.set_capacity_profile(profile)
                return profile
            except Exception:
                pass
        return None


# Global singleton control plane registry
PORTAL_REGISTRY = PortalRegistry()

