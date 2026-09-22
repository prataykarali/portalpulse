"""PortalPulse Universal Connector SDK.

Allows any host portal (Nirantar, University ERP, eCommerce, Gov Portal)
to connect into the PortalPulse Autonomous SRE & Control Tower platform via a
standardized protocol without any host-specific code inside PortalPulse core.
"""

from __future__ import annotations

from portalpulse_sdk.agent import PortalPulseAgent
from portalpulse_sdk.discovery import detect_cgroup_limits, discover_resource_envelope
from portalpulse_sdk.interface import BasePortalConnector
from portalpulse_sdk.middleware import (
    GLOBAL_SESSION_TRACKER,
    ActiveSessionTracker,
    DynamicRateLimiter,
    PortalPulseSessionMiddleware,
    VirtualWaitingRoom,
    render_waiting_room_html,
)
from portalpulse_sdk.schema import (
    ActionCommand,
    ActionResult,
    CapacityProfile,
    DependencyGraphSpec,
    PortalCapabilities,
    ResourceProfile,
    UniversalTelemetry,
)

__all__ = [
    "PortalPulseAgent",
    "BasePortalConnector",
    "UniversalTelemetry",
    "PortalCapabilities",
    "DependencyGraphSpec",
    "ActionCommand",
    "ActionResult",
    "ResourceProfile",
    "CapacityProfile",
    "discover_resource_envelope",
    "detect_cgroup_limits",
    "ActiveSessionTracker",
    "DynamicRateLimiter",
    "VirtualWaitingRoom",
    "render_waiting_room_html",
    "PortalPulseSessionMiddleware",
    "GLOBAL_SESSION_TRACKER",
]
