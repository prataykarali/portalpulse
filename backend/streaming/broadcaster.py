"""PortalPulse Real-time Event Streaming & SSE Broadcaster.

Fulfills PRD-03 & Command Center Requirements:
- Real-time Server-Sent Events (SSE) server -> browser.
- Publishes structured events for all 13 core domains:
  1. telemetry
  2. traffic
  3. control_cycle
  4. forecast
  5. anomaly
  6. rca
  7. action
  8. safety
  9. actuation
  10. warning
  11. recovery
  12. transaction
  13. system_state
- Automatic reconnect support (Last-Event-ID replay from bounded buffer).
- Periodic heartbeats / pings to prevent proxy/socket dropouts.
- Bounded client queues (maxlen=100) with non-blocking put to prevent slow consumers
  from leaking memory or blocking model inference.
- Multi-client fanout and clean disconnect cleanup.
"""

from __future__ import annotations

import asyncio
import collections
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Dict, List, Optional, Set

logger = logging.getLogger("portalpulse.streaming")


def format_sse(event_type: str, data: Any, event_id: Optional[int] = None) -> str:
    """Format an event according to the W3C SSE standard."""
    lines: List[str] = []
    if event_id is not None:
        lines.append(f"id: {event_id}")
    lines.append(f"event: {event_type}")
    try:
        json_str = json.dumps(data, default=str)
    except Exception as exc:
        logger.warning(f"[STREAM] JSON serialization fallback: {exc}")
        json_str = json.dumps({"raw": str(data)})
    lines.append(f"data: {json_str}")
    return "\n".join(lines) + "\n\n"


class StreamBroadcaster:
    """High-performance non-blocking SSE event broadcaster with bounded buffers."""

    def __init__(self, history_buffer_size: int = 250, client_queue_size: int = 100) -> None:
        self.history_buffer_size = history_buffer_size
        self.client_queue_size = client_queue_size
        self._subscribers: Set[asyncio.Queue[Dict[str, Any]]] = set()
        self._history: collections.deque[Dict[str, Any]] = collections.deque(maxlen=history_buffer_size)
        self._event_counter: int = 0
        self._event_type_counts: Dict[str, int] = collections.defaultdict(int)
        self._started_at: float = time.monotonic()
        self._is_shutdown: bool = False

    @property
    def active_subscribers_count(self) -> int:
        return len(self._subscribers)

    def publish(self, event_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Publish an event non-blockingly to all active subscribers.

        Guaranteed NEVER to block model inference or execution loops.
        """
        if self._is_shutdown:
            return data

        self._event_counter += 1
        event_id = self._event_counter
        self._event_type_counts[event_type] += 1

        payload = dict(data)
        if "type" not in payload:
            payload["type"] = event_type
        if "timestamp" not in payload:
            payload["timestamp"] = datetime.now(timezone.utc).isoformat()

        envelope = {
            "id": event_id,
            "type": event_type,
            "data": payload,
        }

        # Store in bounded history ring buffer
        self._history.append(envelope)

        # Non-blocking fan-out to all active client queues
        dead_queues: List[asyncio.Queue[Dict[str, Any]]] = []
        for q in list(self._subscribers):
            try:
                # If client queue is full, drop the oldest event to prevent memory accumulation
                if q.full():
                    try:
                        q.get_nowait()
                    except asyncio.QueueEmpty:
                        pass
                q.put_nowait(envelope)
            except Exception as e:
                logger.debug(f"[STREAM] Dropping unresponsive subscriber queue: {e}")
                dead_queues.append(q)

        for dq in dead_queues:
            self._subscribers.discard(dq)

        return payload

    # -----------------------------------------------------------------------
    # TYPED PUBLISHING HELPERS FOR THE 13 MANDATORY DOMAINS
    # -----------------------------------------------------------------------
    def publish_telemetry(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return self.publish("telemetry", data)

    def publish_traffic(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return self.publish("traffic", data)

    def publish_control_cycle(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return self.publish("control_cycle", data)

    def publish_forecast(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return self.publish("forecast", data)

    def publish_anomaly(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return self.publish("anomaly", data)

    def publish_rca(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return self.publish("rca", data)

    def publish_action(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return self.publish("action", data)

    def publish_safety(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return self.publish("safety", data)

    def publish_actuation(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return self.publish("actuation", data)

    def publish_warning(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return self.publish("warning", data)

    def publish_recovery(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return self.publish("recovery", data)

    def publish_transaction(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return self.publish("transaction", data)

    def publish_system_state(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return self.publish("system_state", data)

    # -----------------------------------------------------------------------
    # SUBSCRIBER LIFECYCLE
    # -----------------------------------------------------------------------
    async def register(self) -> asyncio.Queue[Dict[str, Any]]:
        """Register a new subscriber queue."""
        q: asyncio.Queue[Dict[str, Any]] = asyncio.Queue(maxsize=self.client_queue_size)
        self._subscribers.add(q)
        logger.debug(f"[STREAM] Client connected. Total active subscribers: {len(self._subscribers)}")
        return q

    def unregister(self, q: asyncio.Queue[Dict[str, Any]]) -> None:
        """Unregister a subscriber queue."""
        self._subscribers.discard(q)
        logger.debug(f"[STREAM] Client disconnected. Total active subscribers: {len(self._subscribers)}")

    def get_history_since(self, last_event_id: int) -> List[Dict[str, Any]]:
        """Retrieve missed events for automatic client reconnection."""
        return [evt for evt in self._history if evt["id"] > last_event_id]

    async def sse_generator(
        self,
        last_event_id: Optional[int] = None,
        heartbeat_interval: float = 10.0,
    ) -> AsyncGenerator[str, None]:
        """Async generator yielding standard SSE formatted text."""
        q = await self.register()
        try:
            # If client reconnected with Last-Event-ID, replay missed events from bounded history
            if last_event_id is not None:
                missed = self.get_history_since(last_event_id)
                for item in missed:
                    yield format_sse(item["type"], item["data"], item["id"])
            else:
                # Send immediate initial system_state event on connection
                now_iso = datetime.now(timezone.utc).isoformat()
                yield format_sse("system_state", {
                    "type": "system_state",
                    "timestamp": now_iso,
                    "connected": True,
                    "active_subscribers": len(self._subscribers),
                    "message": "PortalPulse SSE Stream Connected",
                })

            while not self._is_shutdown:
                try:
                    envelope = await asyncio.wait_for(q.get(), timeout=heartbeat_interval)
                    if envelope.get("__shutdown__"):
                        break
                    yield format_sse(envelope["type"], envelope["data"], envelope["id"])
                except asyncio.TimeoutError:
                    # Periodic heartbeat comment + ping event to keep proxy/connection alive
                    now_iso = datetime.now(timezone.utc).isoformat()
                    yield f": heartbeat {now_iso}\n\n"
                    yield format_sse("ping", {
                        "type": "ping",
                        "timestamp": now_iso,
                        "active_subscribers": len(self._subscribers),
                    })
        except asyncio.CancelledError:
            pass
        finally:
            self.unregister(q)

    async def shutdown(self) -> None:
        """Gracefully close all subscriber queues."""
        self._is_shutdown = True
        for q in list(self._subscribers):
            try:
                q.put_nowait({"__shutdown__": True})
            except Exception:
                pass
        self._subscribers.clear()
        logger.info("[STREAM] StreamBroadcaster shut down cleanly.")

    def reset(self) -> None:
        """Reset state (useful in tests)."""
        self._subscribers.clear()
        self._history.clear()
        self._event_counter = 0
        self._event_type_counts.clear()
        self._is_shutdown = False

    def get_stats(self) -> Dict[str, Any]:
        """Return operational telemetry of the SSE streaming subsystem."""
        uptime = round(time.monotonic() - self._started_at, 1)
        return {
            "active_subscribers": len(self._subscribers),
            "total_events_published": self._event_counter,
            "history_buffer_len": len(self._history),
            "history_buffer_capacity": self.history_buffer_size,
            "event_type_counts": dict(self._event_type_counts),
            "uptime_seconds": uptime,
            "is_shutdown": self._is_shutdown,
        }


# Global singleton broadcaster instance
STREAM_BROADCASTER = StreamBroadcaster()
