"""Pydantic models for the PortalPulse Multi-Portal Control Plane."""

from __future__ import annotations

from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from portalpulse_sdk.schema import (
    DependencyGraphSpec,
    PortalCapabilities,
    UniversalTelemetry,
)


class PortalStatus(str, Enum):
    """Operational connection status of a registered portal."""

    ONLINE = "ONLINE"
    DEGRADED = "DEGRADED"
    OFFLINE = "OFFLINE"
    PENDING_VERIFICATION = "PENDING_VERIFICATION"


class ConnectionLifecycleState(str, Enum):
    """State machine governing portal connectivity lifecycle."""

    DISCOVERING = "DISCOVERING"
    AUTHENTICATING = "AUTHENTICATING"
    SCHEMA_VALIDATED = "SCHEMA_VALIDATED"
    CAPABILITIES_DISCOVERED = "CAPABILITIES_DISCOVERED"
    DEPENDENCIES_DISCOVERED = "DEPENDENCIES_DISCOVERED"
    TELEMETRY_VERIFIED = "TELEMETRY_VERIFIED"
    HEALTH_CHECKED = "HEALTH_CHECKED"
    CONNECTED = "CONNECTED"
    TELEMETRY_LOST = "TELEMETRY_LOST"
    DEGRADED = "DEGRADED"
    OFFLINE = "OFFLINE"


class ProvisionKeyRequest(BaseModel):
    """Request payload to provision a permanent connector API key."""

    portal_id: str = Field(..., description="Unique alphanumeric identifier (e.g. 'nirantar')")
    portal_name: str = Field(..., description="Human-readable portal name")
    environment: str = Field(default="production", description="Environment tier (production, staging, dev)")


class ProvisionKeyResponse(BaseModel):
    """Response returned upon provisioning a permanent connector API key."""

    portal_id: str
    api_key: str
    environment: str
    created_at: str
    instructions: str = "Store this API key securely. Present it as X-API-Key header or in the registration payload."


class PortalRegistrationRequest(BaseModel):
    """Request payload to register a new host portal with the control plane."""

    portal_id: str = Field(..., description="Unique alphanumeric identifier (e.g. 'nirantar')")
    portal_name: str = Field(..., description="Human-readable portal name (e.g. 'Nirantar Railway ERP')")
    connector_type: str = Field(
        default="python_sdk", description="Connector implementation type (python_sdk, rest_agent, kubernetes)"
    )
    schema_version: str = Field(default="v1", description="Telemetry contract schema version announced by connector")
    telemetry_interval: int = Field(default=5, ge=1, le=300, description="Reporting interval in seconds")
    capabilities: PortalCapabilities = Field(
        default_factory=PortalCapabilities, description="Infrastructure capabilities exposed by host"
    )
    dependencies: DependencyGraphSpec = Field(
        default_factory=DependencyGraphSpec, description="Topological dependency graph of the portal"
    )
    endpoint_url: Optional[str] = Field(
        default=None, description="Optional webhook URL for remote action dispatch"
    )
    api_key: Optional[str] = Field(
        default=None, description="Pre-shared connector authentication key"
    )


class PortalRegistrationResponse(BaseModel):
    """Acknowledgment payload returned upon successful portal registration handshake."""

    status: str = "CONNECTED"
    portal_id: str
    portal_name: str
    api_key: str
    portalpulse_session: str
    accepted_schema_version: str = "v1"
    telemetry_interval: int = 5
    connection_state: str = "CONNECTED"
    registered_at: str
    discovered_capabilities: PortalCapabilities
    permitted_actions: List[str]
    masked_actions: List[str]
    supported_actions: List[str] = Field(default_factory=list)
    unsupported_actions: List[str] = Field(default_factory=list)


class ActionMask(BaseModel):
    """Boolean action mask vector corresponding to the 11 discrete SREAction indices."""

    portal_id: str
    mask_vector: List[bool] = Field(
        ..., description="11-element boolean list (True=Permitted, False=Masked Out)"
    )
    permitted_actions: List[str]
    masked_actions: List[str]


class MaskedRecommendation(BaseModel):
    """Action intelligence policy outcome after applying the portal-specific action mask."""

    portal_id: str
    raw_action: str = Field(..., description="Action chosen by neural network before capability masking")
    raw_confidence: float = Field(..., description="Raw softmax probability of raw action")
    effective_action: str = Field(..., description="Final permitted action after capability masking")
    effective_confidence: float = Field(
        ..., description="Re-normalized probability of the effective action"
    )
    was_masked: bool = Field(
        ..., description="True if the raw recommendation was overridden due to missing capabilities"
    )
    masking_rationale: str = Field(..., description="Human-readable explanation of the masking logic")
    masked_actions: List[str]
    effective_probabilities: Dict[str, float]


class PortalInfo(BaseModel):
    """Current state and metadata for a registered portal."""

    portal_id: str
    portal_name: str
    connector_type: str
    status: PortalStatus
    connection_state: ConnectionLifecycleState = ConnectionLifecycleState.CONNECTED
    schema_version: str = "v1"
    telemetry_interval: int = 5
    capabilities: PortalCapabilities
    dependencies: DependencyGraphSpec
    permitted_actions: List[str] = Field(default_factory=list)
    masked_actions: List[str] = Field(default_factory=list)
    supported_actions: List[str] = Field(default_factory=list)
    unsupported_actions: List[str] = Field(default_factory=list)
    state_history: List[Dict[str, str]] = Field(default_factory=list)
    registered_at: str
    last_heartbeat: str
    telemetry_count: int
    latest_telemetry: Optional[UniversalTelemetry] = None


class PortalListResponse(BaseModel):
    """Catalog response containing all registered portals."""

    total_portals: int
    portals: List[PortalInfo]
