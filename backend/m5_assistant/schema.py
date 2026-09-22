"""Pydantic schemas for PortalPulse Module 5: AI Operations Assistant & RAG Copilot."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class UserChatMessage(BaseModel):
    """Single chat message in a conversation thread."""

    role: MessageRole
    content: str
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 UTC timestamp",
    )


class DocumentChunk(BaseModel):
    """Knowledge base chunk retrieved from secure_action.md or SRE runbooks."""

    chunk_id: str
    title: str
    section: str
    content: str
    tags: List[str]
    relevance_score: float = Field(..., ge=0.0, le=1.0)


class ChatRequest(BaseModel):
    """Operator chat query payload."""

    message: str = Field(..., min_length=1, description="Operator question or operational prompt")
    history: Optional[List[UserChatMessage]] = Field(
        default=None, description="Prior conversation context"
    )
    session_id: Optional[str] = Field(default="default_sre_session", description="Session identifier")


class ChatResponse(BaseModel):
    """AI Assistant response with grounded context and recommended actions."""

    reply: str
    intent: str
    retrieved_docs: List[DocumentChunk]
    suggested_actions: List[str]
    system_status: str
    requires_operator_action: bool
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class IncidentBrief(BaseModel):
    """Executive incident briefing summarizing current system health, predictions, and recommendations."""

    brief_id: str
    timestamp: str
    system_status: str
    headline: str
    executive_summary: str
    key_metrics: Dict[str, Any]
    projected_forecast_15m: Dict[str, Any]
    anomaly_assessment: Dict[str, Any]
    root_cause_diagnosis: Dict[str, Any]
    prescribed_action: Dict[str, Any]
    human_approval_required: bool
    governance_notes: str


class SearchDocsRequest(BaseModel):
    """Search request to knowledge base."""

    query: str
    top_k: int = Field(default=3, ge=1, le=10)


class SearchDocsResponse(BaseModel):
    """Search response with relevant documentation chunks."""

    query: str
    results_count: int
    results: List[DocumentChunk]


class TopicCatalogResponse(BaseModel):
    """List of indexed architectural and SRE topics available in knowledge base."""

    total_topics: int
    topics: List[str]
