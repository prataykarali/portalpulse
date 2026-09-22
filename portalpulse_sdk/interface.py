"""Universal Connector Interface for PortalPulse.

Any portal integrates by implementing this contract (or subclassing it),
providing standardized telemetry, capabilities, topology, and action execution.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from portalpulse_sdk.schema import (
    ActionCommand,
    ActionResult,
    CapacityProfile,
    DependencyGraphSpec,
    PortalCapabilities,
    ResourceProfile,
    UniversalTelemetry,
)


class BasePortalConnector(ABC):
    """Abstract interface that every PortalPulse portal connector implements."""

    def __init__(self, portal_id: str, portal_name: str) -> None:
        self.portal_id = portal_id
        self.portal_name = portal_name

    @abstractmethod
    def get_telemetry(self) -> UniversalTelemetry:
        """Fetch or sample current standardized APM telemetry from the host portal."""
        raise NotImplementedError

    @abstractmethod
    def get_capabilities(self) -> PortalCapabilities:
        """Declare the infrastructure actions permitted on this portal."""
        raise NotImplementedError

    @abstractmethod
    def get_dependencies(self) -> DependencyGraphSpec:
        """Expose the topological service dependencies of this portal."""
        raise NotImplementedError

    @abstractmethod
    def get_resources(self) -> ResourceProfile:
        """Discover the host portal's actual resource envelope and architectural limits."""
        raise NotImplementedError

    def get_capacity_profile(self) -> Optional[CapacityProfile]:
        """Return the most recent empirical capacity profile measured via benchmark, if available."""
        return None

    @abstractmethod
    def get_health(self) -> Dict[str, Any]:
        """Perform a quick local health check on the portal's connectors and subsystems."""
        raise NotImplementedError

    @abstractmethod
    def execute_action(self, command: ActionCommand) -> ActionResult:
        """Execute a validated SRE mitigation action on the target portal infrastructure."""
        raise NotImplementedError
