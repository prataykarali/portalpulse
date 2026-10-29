"""
Prototype fairness / access layer.

Simulates traffic demand, booking demand, system capacity, request
priority and queue position so a citizen-first journey stays usable
during high demand.

This is NOT connected to real railway infrastructure.
"""

from __future__ import annotations

import hashlib
import threading
import time
import uuid
from typing import Any, Dict, Optional

DISCLAIMER = (
    "Fair Access is a Nirantar prototype simulation. "
    "It is not connected to real railway infrastructure or IRCTC queues."
)

CAPACITY_BY_LEVEL = {
    "NORMAL": 80,
    "ELEVATED": 28,
    "HIGH": 10,
    "SURGE": 4,
}

DEMAND_BY_LEVEL = {
    "NORMAL": {"traffic_demand": 22, "booking_demand": 14},
    "ELEVATED": {"traffic_demand": 48, "booking_demand": 36},
    "HIGH": {"traffic_demand": 90, "booking_demand": 70},
    "SURGE": {"traffic_demand": 160, "booking_demand": 120},
}

PRIORITY_WEIGHT = {
    "SEARCH_TRAINS": 2,
    "VIEW_TICKET": 1,
    "TRACK_TRAIN": 1,
    "PAYMENT_HELP": 0,
    "BOOK": 3,
    "GENERAL_HELP": 4,
}


class FairAccessLayer:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._demand_level = "NORMAL"
        self._tickets: Dict[str, Dict[str, Any]] = {}
        self._fingerprints: Dict[str, str] = {}
        self._admitted_open = 0

    def set_demand_level(self, level: str) -> Dict[str, Any]:
        cleaned = (level or "NORMAL").upper()
        if cleaned not in CAPACITY_BY_LEVEL:
            cleaned = "NORMAL"
        with self._lock:
            self._demand_level = cleaned
        return self.snapshot()

    def admit(
        self,
        action: str,
        session_id: str,
        origin: Optional[str] = None,
        destination: Optional[str] = None,
        travel_date: Optional[str] = None,
        journey_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        fingerprint = _fingerprint(action, session_id, origin, destination, travel_date)
        now = time.time()
        with self._lock:
            # Keep the public prototype bounded even if clients abandon tickets.
            expired = [key for key, value in self._tickets.items() if now - value.get("createdAt", now) > 3600]
            for key in expired:
                self._tickets.pop(key, None)
            if expired:
                self._fingerprints = {
                    fingerprint: ticket_id
                    for fingerprint, ticket_id in self._fingerprints.items()
                    if ticket_id in self._tickets
                }
            if len(self._tickets) >= 2000:
                oldest = min(self._tickets, key=lambda key: self._tickets[key].get("createdAt", now))
                self._tickets.pop(oldest, None)
                self._fingerprints = {
                    fingerprint: ticket_id
                    for fingerprint, ticket_id in self._fingerprints.items()
                    if ticket_id in self._tickets
                }
            existing_id = self._fingerprints.get(fingerprint)
            if existing_id and existing_id in self._tickets:
                ticket = self._tickets[existing_id]
                ticket = self._refresh_ticket(ticket, now)
                ticket["duplicateSuppressed"] = True
                ticket["journeyId"] = ticket.get("journeyId") or journey_id
                self._tickets[existing_id] = ticket
                return ticket

            level = self._demand_level
            capacity = CAPACITY_BY_LEVEL[level]
            demand = DEMAND_BY_LEVEL[level]
            load = demand["traffic_demand"] + demand["booking_demand"]
            queued_count = sum(1 for t in self._tickets.values() if t["status"] == "QUEUED")
            should_queue = load > capacity or queued_count >= max(1, capacity // 4)

            ticket_id = f"FAQ-{uuid.uuid4().hex[:10].upper()}"
            priority = PRIORITY_WEIGHT.get(action, 3)
            if should_queue:
                position = queued_count + 1
                wait = max(8, position * (6 if level == "SURGE" else 4) + priority)
                ticket = {
                    "ticketId": ticket_id,
                    "status": "QUEUED",
                    "admitted": False,
                    "queuePosition": position,
                    "estimatedWaitSeconds": wait,
                    "requestPriority": priority,
                    "action": action,
                    "sessionId": session_id,
                    "journeyId": journey_id,
                    "origin": origin,
                    "destination": destination,
                    "travelDate": travel_date,
                    "demandLevel": level,
                    "trafficDemand": demand["traffic_demand"],
                    "bookingDemand": demand["booking_demand"],
                    "systemCapacity": capacity,
                    "duplicateSuppressed": False,
                    "createdAt": now,
                    "releaseAt": now + wait,
                    "disclaimer": DISCLAIMER,
                }
            else:
                self._admitted_open += 1
                ticket = {
                    "ticketId": ticket_id,
                    "status": "ADMITTED",
                    "admitted": True,
                    "queuePosition": 0,
                    "estimatedWaitSeconds": 0,
                    "requestPriority": priority,
                    "action": action,
                    "sessionId": session_id,
                    "journeyId": journey_id,
                    "origin": origin,
                    "destination": destination,
                    "travelDate": travel_date,
                    "demandLevel": level,
                    "trafficDemand": demand["traffic_demand"],
                    "bookingDemand": demand["booking_demand"],
                    "systemCapacity": capacity,
                    "duplicateSuppressed": False,
                    "createdAt": now,
                    "releaseAt": now,
                    "disclaimer": DISCLAIMER,
                }
            self._tickets[ticket_id] = ticket
            self._fingerprints[fingerprint] = ticket_id
            return dict(ticket)

    def status(self, ticket_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            ticket = self._tickets.get(ticket_id)
            if not ticket:
                return None
            refreshed = self._refresh_ticket(ticket, time.time())
            self._tickets[ticket_id] = refreshed
            return dict(refreshed)

    def snapshot(self) -> Dict[str, Any]:
        now = time.time()
        with self._lock:
            queued = 0
            admitted = 0
            for ticket_id, ticket in list(self._tickets.items()):
                refreshed = self._refresh_ticket(ticket, now)
                self._tickets[ticket_id] = refreshed
                if refreshed["status"] == "QUEUED":
                    queued += 1
                else:
                    admitted += 1
            level = self._demand_level
            demand = DEMAND_BY_LEVEL[level]
            return {
                "demandLevel": level,
                "trafficDemand": demand["traffic_demand"],
                "bookingDemand": demand["booking_demand"],
                "systemCapacity": CAPACITY_BY_LEVEL[level],
                "queuedRequests": queued,
                "admittedRequests": admitted,
                "disclaimer": DISCLAIMER,
            }

    def _refresh_ticket(self, ticket: Dict[str, Any], now: float) -> Dict[str, Any]:
        ticket = dict(ticket)
        if ticket["status"] == "QUEUED" and now >= ticket.get("releaseAt", now):
            ticket["status"] = "ADMITTED"
            ticket["admitted"] = True
            ticket["queuePosition"] = 0
            ticket["estimatedWaitSeconds"] = 0
            self._admitted_open += 1
            return ticket
        if ticket["status"] == "QUEUED":
            remaining = max(0, int(ticket.get("releaseAt", now) - now))
            ahead = sum(
                1
                for other in self._tickets.values()
                if other["status"] == "QUEUED" and other.get("createdAt", 0) < ticket.get("createdAt", 0)
            )
            ticket["queuePosition"] = ahead + 1
            ticket["estimatedWaitSeconds"] = remaining
            ticket["admitted"] = False
        return ticket


def _fingerprint(
    action: str,
    session_id: str,
    origin: Optional[str],
    destination: Optional[str],
    travel_date: Optional[str],
) -> str:
    raw = "|".join(
        [
            (action or "").upper(),
            session_id or "anon",
            (origin or "").upper(),
            (destination or "").upper(),
            travel_date or "",
        ]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


_LAYER = FairAccessLayer()


def get_fair_access_layer() -> FairAccessLayer:
    return _LAYER
