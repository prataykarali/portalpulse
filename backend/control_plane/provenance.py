"""Telemetry Provenance and Reality Classification Layer for PortalPulse.

Every metric displayed on the dashboard or processed by the ML intelligence layer
must declare its exact provenance and reality tier:
- LIVE_PORTAL: Captured from actual HTTP server requests or OS performance counters
- LIVE_LOCUST: Directly sampled from running Locust worker egress stats
- LIVE_MODEL: Inferred in real-time by a local machine learning model execution
- REAL_LOCAL_FAULT: Physical local environment impact (e.g. sleep delay, semaphore exhaustion)
- SIMULATED_FAULT: Clearly tagged synthetic fault injection
- HISTORICAL: Retrieved from historical persistence tables
- DERIVED: Mathematical formula computed over other raw metrics

Never silently fabricate fallback telemetry without tagging it with SIMULATED provenance.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class ProvenanceTag(str, Enum):
    LIVE_PORTAL = "LIVE_PORTAL"
    LIVE_LOCUST = "LIVE_LOCUST"
    LIVE_MODEL = "LIVE_MODEL"
    REAL_LOCAL_FAULT = "REAL_LOCAL_FAULT"
    SIMULATED_FAULT = "SIMULATED_FAULT"
    HISTORICAL = "HISTORICAL"
    DERIVED = "DERIVED"


class MetricProvenance(BaseModel):
    """Metadata describing the origin, environment, and veracity of a metric."""

    metric: str
    value: Any
    unit: str
    portal: str
    source: str
    timestamp: str
    request_count: int = 0
    environment: str = "local"
    provenance: ProvenanceTag = ProvenanceTag.LIVE_PORTAL
    is_simulated: bool = False
    details: Optional[Dict[str, Any]] = None


class ProvenanceClassifier:
    """Classifies and wraps raw telemetry dicts with formal provenance tags."""

    @staticmethod
    def tag_metric(
        metric: str,
        value: Any,
        unit: str,
        portal: str,
        source: str,
        timestamp: str,
        provenance: ProvenanceTag,
        request_count: int = 0,
        is_simulated: Optional[bool] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> MetricProvenance:
        sim = is_simulated if is_simulated is not None else (provenance == ProvenanceTag.SIMULATED_FAULT)
        return MetricProvenance(
            metric=metric,
            value=value,
            unit=unit,
            portal=portal,
            source=source,
            timestamp=timestamp,
            request_count=request_count,
            environment="local",
            provenance=provenance,
            is_simulated=sim,
            details=details,
        )

    @staticmethod
    def annotate_telemetry_dict(
        data: Dict[str, Any],
        default_provenance: ProvenanceTag = ProvenanceTag.LIVE_PORTAL,
    ) -> Dict[str, Any]:
        """Add global reality provenance block to telemetry responses."""
        is_sim = default_provenance == ProvenanceTag.SIMULATED_FAULT or data.get("is_simulated", False)
        data["_provenance"] = {
            "tag": default_provenance.value if hasattr(default_provenance, "value") else str(default_provenance),
            "is_simulated": is_sim,
            "provenance_badge": "🧪 SIMULATED" if is_sim else "● LIVE",
            "source": data.get("source", "portal_adapter"),
            "environment": data.get("environment", "local"),
        }
        return data


# Convenience alias and functions for test harness and control plane consumers
TaggedMetric = MetricProvenance


def tag_metric(
    value: Any,
    provenance: ProvenanceTag = ProvenanceTag.LIVE_PORTAL,
    source: str = "collector",
    metric: str = "generic_metric",
    unit: str = "count",
    portal: str = "default",
) -> MetricProvenance:
    """Create a validated MetricProvenance instance."""
    return MetricProvenance(
        metric=metric,
        value=value,
        unit=unit,
        portal=portal,
        source=source,
        timestamp=datetime.now(timezone.utc).isoformat(),
        provenance=provenance,
        is_simulated=provenance in (ProvenanceTag.SIMULATED_FAULT,),
    )


def validate_provenance(m: MetricProvenance) -> bool:
    """Validate that a metric has traceable provenance and source metadata."""
    return bool(m.provenance and m.source)

