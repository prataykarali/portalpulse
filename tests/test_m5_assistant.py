"""Unit and integration test suite for PortalPulse Module 5 (AI Operations Assistant & RAG Copilot).

Verifies:
1. SREKnowledgeBase semantic indexing of secure_action.md, topic cataloging, and cosine search.
2. SREOperationsCopilot natural language intent parsing, grounded telemetry reasoning, and incident briefs.
3. FastAPI HTTP endpoints for interactive operator chat, incident briefing, and documentation search.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.app import app
from backend.m1_monitoring.collector import COLLECTOR
from backend.m1_monitoring.schema import RawTelemetry
from backend.m5_assistant.copilot import COPILOT, SREOperationsCopilot
from backend.m5_assistant.knowledge_base import KNOWLEDGE_BASE, SREKnowledgeBase
from backend.m5_assistant.schema import (
    ChatRequest,
    ChatResponse,
    IncidentBrief,
)

client = TestClient(app)


# ---------------------------------------------------------------------------
# Test Fixtures & Seed Telemetry
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session", autouse=True)
def seed_live_telemetry() -> None:
    """Seed telemetry buffer so copilot has live metrics to ground responses."""
    raw = RawTelemetry(
        active_users=45000,
        requests_per_sec=2800.0,
        cpu_percent=88.0,
        ram_percent=62.0,
        network_in=180.0,
        network_out=420.0,
        response_time=920.0,
        throughput=2750.0,
        error_rate=0.018,
        http_5xx=50.0,
        db_latency=45.0,
        db_connections=55.0,
        queue_length=320,
        service_instances=4,
    )
    COLLECTOR.ingest(raw)


# ---------------------------------------------------------------------------
# 1. Knowledge Base Tests
# ---------------------------------------------------------------------------


class TestSREKnowledgeBase:
    """Test suite for semantic indexing and retrieval across secure_action.md."""

    def test_indexing_and_topics(self) -> None:
        kb = SREKnowledgeBase()
        assert len(kb.chunks) >= 5
        assert len(kb.topics) >= 4
        assert any("Autoscaling" in t or "Rate" in t or "Load" in t for t in kb.topics)

    def test_search_rate_limiting(self) -> None:
        results = KNOWLEDGE_BASE.search("token bucket algorithm and burst rate limiting", top_k=2)
        assert len(results) >= 1
        top = results[0]
        assert "rate" in top.title.lower() or "limit" in top.title.lower() or "token" in top.content.lower()
        assert top.relevance_score > 0.0

    def test_search_circuit_breaker(self) -> None:
        results = KNOWLEDGE_BASE.search("circuit breaker tripping and fallback responses", top_k=2)
        assert len(results) >= 1
        top = results[0]
        assert "circuit" in top.title.lower() or "degradation" in top.title.lower() or "breaker" in top.content.lower()

    def test_search_autoscaling(self) -> None:
        results = KNOWLEDGE_BASE.search("horizontal scaling warm pools and predictive autoscaling", top_k=2)
        assert len(results) >= 1
        top = results[0]
        assert "scaling" in top.title.lower() or "autoscaling" in top.section.lower()


# ---------------------------------------------------------------------------
# 2. Copilot Reasoning & Synthesis Tests
# ---------------------------------------------------------------------------


class TestSREOperationsCopilot:
    """Test suite for SRE Copilot conversational reasoning and incident briefing."""

    def test_intent_classification(self) -> None:
        copilot = SREOperationsCopilot()

        assert copilot._classify_intent("Why is the system responding so slowly?") == "ROOT_CAUSE_QUERY"
        assert copilot._classify_intent("What is the predicted traffic at 10m horizon?") == "FORECAST_QUERY"
        assert copilot._classify_intent("What action should we execute right now?") == "ACTION_QUERY"
        assert copilot._classify_intent("What is the current health status?") == "STATUS_CHECK"
        assert copilot._classify_intent("Explain token bucket rate limiting from runbook") == "DOCS_QUERY"
        assert copilot._classify_intent("Hello assistant") == "GENERAL_SRE"

    def test_chat_status_check(self) -> None:
        req = ChatRequest(message="What is the current system health status?")
        res = COPILOT.chat(req)

        assert isinstance(res, ChatResponse)
        assert res.intent == "STATUS_CHECK"
        assert "Ingress Traffic" in res.reply or "System Health" in res.reply
        assert len(res.suggested_actions) >= 1
        assert res.system_status in ["NOMINAL", "WARNING", "CRITICAL"]

    def test_chat_root_cause_diagnosis(self) -> None:
        req = ChatRequest(message="What is the root cause of current degradation?")
        res = COPILOT.chat(req)

        assert isinstance(res, ChatResponse)
        assert res.intent == "ROOT_CAUSE_QUERY"
        assert "Root Cause" in res.reply
        assert "Playbook" in res.reply

    def test_chat_forecast_query(self) -> None:
        req = ChatRequest(message="Can you forecast what will happen to CPU and RPS in 10 minutes?")
        res = COPILOT.chat(req)

        assert isinstance(res, ChatResponse)
        assert res.intent == "FORECAST_QUERY"
        assert "+5 Minutes" in res.reply or "+10 Minutes" in res.reply
        assert "Horizon" in res.reply

    def test_chat_action_query(self) -> None:
        req = ChatRequest(message="What tactical SRE action is recommended?")
        res = COPILOT.chat(req)

        assert isinstance(res, ChatResponse)
        assert res.intent == "ACTION_QUERY"
        assert "Recommended Action" in res.reply
        assert "Tactical Rationale" in res.reply

    def test_generate_incident_brief(self) -> None:
        brief = COPILOT.generate_incident_brief()

        assert isinstance(brief, IncidentBrief)
        assert brief.brief_id.startswith("brief_")
        assert len(brief.headline) > 10
        assert len(brief.executive_summary) > 50
        assert "requests_per_sec" in brief.key_metrics
        assert "rps_5m" in brief.projected_forecast_15m
        assert "primary_root_cause" in brief.root_cause_diagnosis
        assert "action" in brief.prescribed_action
        assert isinstance(brief.human_approval_required, bool)


# ---------------------------------------------------------------------------
# 3. FastAPI HTTP Endpoints Tests
# ---------------------------------------------------------------------------


class TestFastAPIEndpointsM5:
    """Test suite for Module 5 HTTP endpoints."""

    def test_post_chat(self) -> None:
        response = client.post("/api/v1/assistant/chat", json={"message": "What is happening right now?"})
        assert response.status_code == 200
        data = response.json()
        assert "reply" in data
        assert "intent" in data
        assert "retrieved_docs" in data
        assert "suggested_actions" in data

    def test_get_incident_brief(self) -> None:
        response = client.get("/api/v1/assistant/incident-brief")
        assert response.status_code == 200
        data = response.json()
        assert "brief_id" in data
        assert "headline" in data
        assert "executive_summary" in data
        assert "key_metrics" in data
        assert "prescribed_action" in data

    def test_post_knowledge_search(self) -> None:
        payload = {"query": "rate limiting and token bucket", "top_k": 3}
        response = client.post("/api/v1/assistant/knowledge/search", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["results_count"] <= 3
        assert len(data["results"]) >= 1

    def test_get_knowledge_topics(self) -> None:
        response = client.get("/api/v1/assistant/knowledge/topics")
        assert response.status_code == 200
        data = response.json()
        assert data["total_topics"] >= 4
        assert len(data["topics"]) >= 4
