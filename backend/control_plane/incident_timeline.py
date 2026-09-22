"""Incident Timeline Event Engine.

Maintains a continuous, timestamped narrative timeline connecting models, avatars,
telemetry, and physical actuations into one traceable end-to-end story.
"""

from __future__ import annotations

import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class TimelineEvent(BaseModel):
    id: str
    timestamp: str
    stage: str  # TELEMETRY, M2_PREDICT, M3_ANOMALY, M4_RCA, M5_ACTION, M6_SAFETY, M7_ACTUATE, VERIFY, ROLLBACK
    portal_id: str
    message: str
    level: str = "INFO"  # INFO, WARNING, ACTION, SUCCESS, ERROR
    confidence: Optional[float] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class IncidentTimelineManager:
    """Singleton in-memory thread-safe chronological event recorder."""

    def __init__(self, max_events: int = 200) -> None:
        self.max_events = max_events
        self._events: List[TimelineEvent] = []
        self._lock = threading.Lock()
        self._seed_default_events()

    def _seed_default_events(self) -> None:
        now = datetime.now(timezone.utc).strftime("%H:%M:%S")
        self.record_event(
            stage="TELEMETRY",
            portal_id="nirantar",
            message="Autonomous monitoring initialized · nominal baseline established",
            level="INFO",
        )

    def record_event(
        self,
        stage: str,
        portal_id: str,
        message: str,
        level: str = "INFO",
        confidence: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> TimelineEvent:
        event = TimelineEvent(
            id=f"evt_{int(time.time()*1000)}_{len(self._events)}",
            timestamp=datetime.now(timezone.utc).strftime("%H:%M:%S"),
            stage=stage,
            portal_id=portal_id,
            message=message,
            level=level,
            confidence=confidence,
            metadata=metadata or {},
        )
        with self._lock:
            self._events.append(event)
            if len(self._events) > self.max_events:
                self._events.pop(0)
        return event

    def get_events(self, portal_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        with self._lock:
            evts = list(self._events)
        if portal_id:
            evts = [e for e in evts if e.portal_id == portal_id]
        return [e.model_dump() for e in evts[-limit:]]

    def clear(self) -> None:
        with self._lock:
            self._events.clear()
            self._seed_default_events()


TIMELINE_MANAGER = IncidentTimelineManager()
