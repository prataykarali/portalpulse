"""PortalPulse Client Agent.

Embeddable lightweight agent for Python web frameworks (FastAPI, Django, Flask, etc.).
Allows a portal to register with the PortalPulse Control Plane, stream telemetry,
declare its infrastructure capabilities, and handle dispatched SRE actions.
"""

from __future__ import annotations

import json
import logging
import threading
import time
import urllib.error
import urllib.request
import uuid
from typing import Any, Callable, Dict, List, Optional

from portalpulse_sdk.schema import (
    ActionCommand,
    ActionResult,
    DependencyGraphSpec,
    PortalCapabilities,
    UniversalTelemetry,
)

logger = logging.getLogger("portalpulse.agent")
ActionHandler = Callable[[Dict[str, Any]], ActionResult]


class PortalPulseAgent:
    """Lightweight client agent embedded within a portal application."""

    def __init__(
        self,
        portal_id: str,
        portal_name: str,
        control_plane_url: str = "http://localhost:8000",
        api_key: Optional[str] = None,
        capabilities: Optional[PortalCapabilities] = None,
        dependencies: Optional[DependencyGraphSpec] = None,
        telemetry_interval: int = 5,
    ) -> None:
        self.portal_id = portal_id
        self.portal_name = portal_name
        self.control_plane_url = control_plane_url.rstrip("/")
        self.api_key = api_key or f"pp_live_{portal_id}_key"
        self.capabilities = capabilities or PortalCapabilities()
        self.dependencies = dependencies or DependencyGraphSpec()
        self.telemetry_interval = telemetry_interval
        self.action_handlers: Dict[str, ActionHandler] = {}
        self.is_registered: bool = False
        self.session_token: Optional[str] = None
        self.permitted_actions: List[str] = []
        self.masked_actions: List[str] = []
        self._stop_event = threading.Event()
        self._worker_thread: Optional[threading.Thread] = None

    def register_action_handler(self, action_type: str, handler: ActionHandler) -> None:
        """Register a callback function to execute when PortalPulse dispatches an action."""
        self.action_handlers[action_type] = handler
        logger.info("Registered action handler for %s on portal %s", action_type, self.portal_id)

    def dispatch_local_action(self, command: ActionCommand) -> ActionResult:
        """Dispatch an incoming action to the registered local handler."""
        handler = self.action_handlers.get(command.action_type)
        if not handler:
            return ActionResult(
                action_id=command.action_id,
                portal_id=self.portal_id,
                success=False,
                message=f"No local handler registered for action type: {command.action_type}",
            )

        try:
            return handler(command.parameters)
        except Exception as e:
            logger.exception("Error executing action %s: %s", command.action_type, e)
            return ActionResult(
                action_id=command.action_id,
                portal_id=self.portal_id,
                success=False,
                message=f"Action execution raised exception: {str(e)}",
            )

    def connect(self) -> Dict[str, Any]:
        """Perform 7-step handshake with PortalPulse Control Plane."""
        url = f"{self.control_plane_url}/api/v1/portals/register"
        payload = {
            "portal_id": self.portal_id,
            "portal_name": self.portal_name,
            "connector_type": "python_sdk",
            "schema_version": "v1",
            "telemetry_interval": self.telemetry_interval,
            "capabilities": self.capabilities.model_dump(),
            "dependencies": self.dependencies.model_dump(),
            "api_key": self.api_key,
        }
        data_bytes = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "X-API-Key": self.api_key,
        }
        req = urllib.request.Request(url, data=data_bytes, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=10.0) as resp:  # nosec B310
                result = json.loads(resp.read().decode("utf-8"))
                self.session_token = result.get("portalpulse_session")
                self.telemetry_interval = result.get("telemetry_interval", self.telemetry_interval)
                self.permitted_actions = result.get("permitted_actions", [])
                self.masked_actions = result.get("masked_actions", [])
                self.is_registered = True
                logger.info("Connected to PortalPulse Control Plane. Session: %s", self.session_token)
                return result
        except Exception as e:
            logger.error("Failed to connect to PortalPulse Control Plane at %s: %s", url, e)
            raise

    def emit_telemetry(self, telemetry: UniversalTelemetry | Dict[str, Any]) -> Dict[str, Any]:
        """Send a standardized telemetry step to PortalPulse Ingestion Collector."""
        url = f"{self.control_plane_url}/api/v1/portals/{self.portal_id}/telemetry"
        if isinstance(telemetry, UniversalTelemetry):
            payload_dict = telemetry.model_dump()
        else:
            payload_dict = dict(telemetry)
            if "portal_id" not in payload_dict:
                payload_dict["portal_id"] = self.portal_id

        data_bytes = json.dumps(payload_dict).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "X-API-Key": self.api_key,
        }
        req = urllib.request.Request(url, data=data_bytes, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=10.0) as resp:  # nosec B310
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as he:
            err_body = he.read().decode("utf-8")
            logger.error("HTTP %s from telemetry endpoint: %s", he.code, err_body)
            raise ValueError(f"Telemetry ingestion rejected with {he.code}: {err_body}") from he
        except Exception as e:
            logger.error("Failed to emit telemetry to %s: %s", url, e)
            raise

    def heartbeat(self) -> Dict[str, Any]:
        """Send lightweight liveness heartbeat to maintain active session."""
        url = f"{self.control_plane_url}/api/v1/portals/{self.portal_id}/heartbeat"
        req = urllib.request.Request(url, data=b"", headers={"X-API-Key": self.api_key}, method="POST")
        with urllib.request.urlopen(req, timeout=5.0) as resp:  # nosec B310
            return json.loads(resp.read().decode("utf-8"))

    def start(
        self,
        interval: Optional[int] = None,
        telemetry_provider: Optional[Callable[[], UniversalTelemetry]] = None,
    ) -> None:
        """Start background daemon thread streaming telemetry periodically."""
        if not self.is_registered:
            self.connect()

        loop_interval = interval or self.telemetry_interval
        self._stop_event.clear()

        def _worker() -> None:
            logger.info("Started PortalPulse telemetry background worker (interval=%ss)", loop_interval)
            while not self._stop_event.is_set():
                try:
                    if telemetry_provider:
                        tel = telemetry_provider()
                    else:
                        tel = self.build_telemetry(
                            active_users=1200,
                            requests_per_sec=180.0,
                            cpu_percent=45.0,
                            ram_percent=52.0,
                            latency_ms=120.0,
                            throughput=178.0,
                            error_rate=0.001,
                        )
                    self.emit_telemetry(tel)
                except Exception as exc:
                    logger.warning("Telemetry emission cycle encountered error: %s", exc)
                self._stop_event.wait(loop_interval)

        self._worker_thread = threading.Thread(target=_worker, daemon=True, name=f"pp-agent-{self.portal_id}")
        self._worker_thread.start()

    def stop(self) -> None:
        """Gracefully halt the background telemetry worker thread."""
        self._stop_event.set()
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=2.0)
            logger.info("Stopped PortalPulse telemetry worker for %s", self.portal_id)

    def build_telemetry(
        self,
        active_users: int,
        requests_per_sec: float,
        cpu_percent: float,
        ram_percent: float,
        latency_ms: float,
        throughput: float,
        error_rate: float,
        http_5xx: float = 0.0,
        db_latency_ms: float = 0.0,
        db_connections: float = 0.0,
        queue_length: int = 0,
        service_instances: int = 4,
        network_in_mb: float = 10.0,
        network_out_mb: float = 25.0,
        tags: Optional[Dict[str, str]] = None,
    ) -> UniversalTelemetry:
        """Convenience factory method to generate a typed UniversalTelemetry payload."""
        return UniversalTelemetry(
            portal_id=self.portal_id,
            active_users=active_users,
            requests_per_sec=requests_per_sec,
            cpu_percent=cpu_percent,
            ram_percent=ram_percent,
            latency_ms=latency_ms,
            throughput=throughput,
            error_rate=error_rate,
            http_5xx=http_5xx,
            db_latency_ms=db_latency_ms,
            db_connections=db_connections,
            queue_length=queue_length,
            service_instances=service_instances,
            network_in_mb=network_in_mb,
            network_out_mb=network_out_mb,
            tags=tags or {},
        )
