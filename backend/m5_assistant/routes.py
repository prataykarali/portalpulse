"""FastAPI HTTP routes for PortalPulse Module 5: AI Operations Assistant & RAG Copilot."""

from __future__ import annotations

from fastapi import APIRouter

from backend.m5_assistant.copilot import COPILOT
from backend.m5_assistant.knowledge_base import KNOWLEDGE_BASE
from backend.m5_assistant.schema import (
    ChatRequest,
    ChatResponse,
    IncidentBrief,
    SearchDocsRequest,
    SearchDocsResponse,
    TopicCatalogResponse,
)

router = APIRouter(prefix="/api/v1/assistant", tags=["Module 5: AI Operations Assistant"])


@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="Interactive dialogue with SRE Copilot grounded in telemetry and secure_action.md",
)
def post_assistant_chat(request: ChatRequest) -> ChatResponse:
    """Answers operator queries with real-time telemetry metrics and runbook context."""
    return COPILOT.chat(request)


@router.get(
    "/incident-brief",
    response_model=IncidentBrief,
    summary="Generate comprehensive executive incident briefing across all modules",
)
def get_incident_brief() -> IncidentBrief:
    """Synthesizes live telemetry, load forecast, anomaly RCA, and prescriptive actions."""
    return COPILOT.generate_incident_brief()


@router.post(
    "/knowledge/search",
    response_model=SearchDocsResponse,
    summary="Semantic vector search across secure_action.md SRE runbooks",
)
def post_search_knowledge(request: SearchDocsRequest) -> SearchDocsResponse:
    """Searches SRE operational knowledge base with TF-IDF cosine ranking."""
    results = KNOWLEDGE_BASE.search(request.query, top_k=request.top_k)
    return SearchDocsResponse(
        query=request.query,
        results_count=len(results),
        results=results,
    )


@router.get(
    "/knowledge/topics",
    response_model=TopicCatalogResponse,
    summary="List all indexed architectural topics in the SRE runbook library",
)
def get_knowledge_topics() -> TopicCatalogResponse:
    """Returns all sections indexed from secure_action.md and system documentation."""
    return TopicCatalogResponse(
        total_topics=len(KNOWLEDGE_BASE.topics),
        topics=KNOWLEDGE_BASE.topics,
    )
