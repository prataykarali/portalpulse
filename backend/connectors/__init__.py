"""PortalPulse Reference Connectors Package.

Contains reference implementations of BasePortalConnector for distinct portal archetypes:
1. NirantarConnector (Gov/Railway high-concurrency ERP with full capabilities)
2. CollegePortalConnector (Constrained university ERP with disabled DB replicas & cache)
3. ECommerceConnector (Microservices eCommerce store with feature flag toggling)
"""

from __future__ import annotations

from backend.connectors.college_portal import CollegePortalConnector
from backend.connectors.ecommerce import ECommerceConnector
from backend.connectors.nirantar import NirantarConnector

__all__ = [
    "NirantarConnector",
    "CollegePortalConnector",
    "ECommerceConnector",
]
