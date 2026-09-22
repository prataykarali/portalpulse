"""Autonomous SRE Operations Copilot and Technical Explanation Engine.

Synthesizes telemetry signals from M1-M4, integrates RAG context from secure_action.md,
and provides conversational technical reasoning and automated executive incident briefs.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import List, Optional, Tuple

from backend.m1_monitoring.collector import COLLECTOR
from backend.m1_monitoring.schema import LiveTelemetryStatus, RawTelemetry
from backend.m2_prediction.forecaster import FORECASTER
from backend.m2_prediction.schema import ForecastResult
from backend.m3_anomaly_rca.anomaly_detector import DETECTOR
from backend.m3_anomaly_rca.rca_classifier import RCA_CLASSIFIER
from backend.m3_anomaly_rca.schema import AnomalyResult, RCAResult
from backend.m4_action_intelligence.action_engine import ACTION_ENGINE
from backend.m4_action_intelligence.schema import ActionRecommendation
from backend.m5_assistant.knowledge_base import KNOWLEDGE_BASE, SREKnowledgeBase
from backend.m5_assistant.schema import (
    ChatRequest,
    ChatResponse,
    IncidentBrief,
)


class SREOperationsCopilot:
    """Intelligent operational assistant grounding conversational responses in live telemetry and runbooks."""

    def __init__(self, knowledge_base: Optional[SREKnowledgeBase] = None) -> None:
        self.kb = knowledge_base or KNOWLEDGE_BASE

    def _collect_live_context(
        self,
    ) -> Tuple[
        Optional[RawTelemetry],
        Optional[LiveTelemetryStatus],
        Optional[ForecastResult],
        Optional[AnomalyResult],
        Optional[RCAResult],
        Optional[ActionRecommendation],
    ]:
        """Query live state across all PortalPulse modules."""
        raw = COLLECTOR.get_latest_telemetry()
        status_info = COLLECTOR.get_latest_status()

        if raw is None:
            return None, None, None, None, None, None

        derived = COLLECTOR.compute_derived_features(raw)
        forecast = FORECASTER.predict(raw, derived)
        anomaly = DETECTOR.detect(raw)
        rca = RCA_CLASSIFIER.classify(raw)
        action = ACTION_ENGINE.recommend(raw, derived=derived, forecast=forecast, rca=rca)

        return raw, status_info, forecast, anomaly, rca, action

    def _classify_intent(self, message: str) -> str:
        """Classify operator intent into operational query categories."""
        msg = message.lower()
        if any(w in msg for w in ["why", "root cause", "rca", "failing", "broken", "cause"]):
            return "ROOT_CAUSE_QUERY"
        if any(w in msg for w in ["predict", "forecast", "future", "soon", "10m", "15m", "ahead"]):
            return "FORECAST_QUERY"
        if any(w in msg for w in ["action", "recommend", "should we", "do now", "mitigate", "fix"]):
            return "ACTION_QUERY"
        if any(w in msg for w in ["status", "happening", "right now", "health", "how is", "metrics"]):
            return "STATUS_CHECK"
        if any(w in msg for w in ["explain", "runbook", "secure_action", "token bucket", "circuit breaker", "anycast"]):
            return "DOCS_QUERY"
        return "GENERAL_SRE"

    def chat(self, request: ChatRequest) -> ChatResponse:
        """Process natural language operator question with grounded telemetry and RAG documentation."""
        intent = self._classify_intent(request.message)
        raw, status_info, forecast, anomaly, rca, action = self._collect_live_context()

        # Retrieve relevant RAG documentation chunks
        doc_chunks = self.kb.search(request.message, top_k=2)

        # Build response based on intent and live telemetry
        if raw is None or status_info is None or forecast is None or anomaly is None or rca is None or action is None:
            return ChatResponse(
                reply=(
                    "The PortalPulse collector buffer is currently empty. Synthetic telemetry is initializing. "
                    "Once telemetry starts streaming, I will provide full diagnostic explanations."
                ),
                intent=intent,
                retrieved_docs=doc_chunks,
                suggested_actions=["Seed Telemetry", "Check Platform Status"],
                system_status="INITIALIZING",
                requires_operator_action=False,
            )

        status_str = status_info.health_status.value
        suggested: List[str] = []

        if intent == "STATUS_CHECK":
            reply = (
                f"### System Health Summary: **{status_str}**\n\n"
                f"- **Ingress Traffic:** {raw.requests_per_sec:,.0f} RPS ({raw.active_users:,.0f} active users)\n"
                f"- **Compute Utilization:** CPU at **{raw.cpu_percent:.1f}%**, RAM at **{raw.ram_percent:.1f}%** across {int(raw.service_instances)} replicas\n"
                f"- **Latency & Quality:** p95 Latency is **{raw.response_time:.0f} ms**, HTTP 5xx error rate is **{raw.error_rate * 100.0:.2f}%**\n"
                f"- **Database Pool:** {raw.db_connections:.1f}% pool utilization, DB latency {raw.db_latency:.1f} ms\n"
                f"- **Queue Backlog:** {int(raw.queue_length)} pending requests in buffer\n\n"
            )
            if anomaly.is_anomaly:
                reply += (
                    f"> ⚠️ **Anomaly Detected!** Isolation Forest score: `{anomaly.anomaly_score:.2f}` ({anomaly.severity}). "
                    f"RCA attribution points to **{rca.primary_root_cause.value}** with {rca.confidence * 100.0:.1f}% confidence."
                )
                suggested.append(f"Execute {action.primary_action.value}")
            else:
                reply += "All primary SLAs (latency < 800ms, CPU < 85%, error rate < 1.0%) are currently satisfied."
                suggested.append("Continue Monitoring")

        elif intent == "ROOT_CAUSE_QUERY":
            reply = (
                f"### Root Cause Analysis & Topological Diagnostics\n\n"
                f"- **Primary Root Cause:** `{rca.primary_root_cause.value}` (Attribution Confidence: **{rca.confidence * 100.0:.1f}%**)\n"
                f"- **Affected Architectural Tier:** `{rca.root_cause_tier}`\n"
                f"- **Causal Propagation Path:** {' ➔ '.join(rca.causal_propagation_chain)}\n"
                f"- **Anomaly Score:** `{anomaly.anomaly_score:.2f}` (Severity: {anomaly.severity})\n\n"
                f"**Tactical Remediation Playbook:**\n{rca.recommended_mitigation}\n"
            )
            suggested.append(f"Apply Playbook: {action.primary_action.value}")
            suggested.append("Inspect Causal Topology")

        elif intent == "FORECAST_QUERY":
            reply = (
                f"### Multi-Horizon XGBoost Telemetry Forecast\n\n"
                f"- **+5 Minutes Horizon:**\n"
                f"  - Ingress RPS: **{forecast.rps_5m:,.0f} RPS** (Growth: {((forecast.rps_5m - raw.requests_per_sec) / max(raw.requests_per_sec, 1.0)) * 100.0:+.1f}%)\n"
                f"  - Worker CPU: **{forecast.cpu_5m:.1f}%**\n"
                f"  - Expected Latency: **{forecast.latency_5m:.0f} ms**\n"
                f"- **+10 Minutes Horizon:** {forecast.rps_10m:,.0f} RPS | CPU: {forecast.cpu_10m:.1f}% | Latency: {forecast.latency_10m:.0f} ms\n"
                f"- **+15 Minutes Horizon:** {forecast.rps_15m:,.0f} RPS | CPU: {forecast.cpu_15m:.1f}% | Latency: {forecast.latency_15m:.0f} ms\n\n"
                f"- **Capacity Assessment:** Safe concurrent capacity is **{forecast.safe_capacity:,.0f} users** "
                f"(Capacity Pressure Index: `{forecast.capacity_pressure_index:.2f}`, Risk: **{forecast.risk_level.value}**).\n"
            )
            suggested.append("View Horizon Graphs")

        elif intent == "ACTION_QUERY":
            requires_hitl = action.requires_human_approval
            reply = (
                f"### Prescriptive Action Intelligence Recommendation\n\n"
                f"- **Recommended Action:** `{action.primary_action.value}`\n"
                f"- **Policy Network Confidence:** **{action.confidence * 100.0:.1f}%**\n"
                f"- **Estimated Blast Radius:** **{action.estimated_blast_radius}**\n"
                f"- **Human Approval Required:** {'**YES (Operator Confirmation Enforced)**' if requires_hitl else 'No (Auto-executable)'}\n\n"
                f"**Tactical Rationale:**\n{action.tactical_rationale}\n\n"
            )
            if requires_hitl:
                reply += (
                    "> 🛡️ **Safety Guardrail (`secure_action.md`):** High blast-radius or sub-80% confidence actions "
                    "require explicit 2-phase human operator sign-off before dispatching to infrastructure actuators."
                )
                suggested.append(f"Approve {action.primary_action.value}")
                suggested.append("Reject Action")
            else:
                suggested.append(f"Execute {action.primary_action.value}")

        elif intent == "DOCS_QUERY":
            top_doc = doc_chunks[0] if doc_chunks else None
            if top_doc:
                reply = (
                    f"### Operational Knowledge: {top_doc.title}\n"
                    f"*Section: {top_doc.section} (Relevance Score: {top_doc.relevance_score:.2f})*\n\n"
                    f"{top_doc.content}\n\n"
                    f"**Platform Mapping:** Currently, the system is operating at {raw.requests_per_sec:,.0f} RPS with "
                    f"recommended tactical mitigation `{action.primary_action.value}`."
                )
            else:
                reply = "Consulting `secure_action.md` knowledge base. Please query specific SRE patterns."
            suggested.append("Search Related Runbooks")

        else:
            reply = (
                f"I am monitoring PortalPulse in real time. Current status is **{status_str}** with "
                f"**{raw.requests_per_sec:,.0f} RPS** and **{raw.cpu_percent:.1f}% CPU**. "
                f"Recommended action is `{action.primary_action.value}`."
            )
            suggested.extend(["Get Incident Brief", "Explain Root Cause", "Show Forecast"])

        return ChatResponse(
            reply=reply,
            intent=intent,
            retrieved_docs=doc_chunks,
            suggested_actions=suggested,
            system_status=status_str,
            requires_operator_action=action.requires_human_approval,
        )

    def generate_incident_brief(self) -> IncidentBrief:
        """Synthesize an executive incident briefing combining telemetry, forecast, RCA, and policy recommendations."""
        raw, status_info, forecast, anomaly, rca, action = self._collect_live_context()

        brief_id = f"brief_{uuid.uuid4().hex[:8]}"
        now_iso = datetime.now(timezone.utc).isoformat()

        if raw is None or status_info is None or forecast is None or anomaly is None or rca is None or action is None:
            return IncidentBrief(
                brief_id=brief_id,
                timestamp=now_iso,
                system_status="NO_DATA",
                headline="Platform Telemetry Offline",
                executive_summary="No telemetry data is currently being ingested by the circular ring buffer.",
                key_metrics={},
                projected_forecast_15m={},
                anomaly_assessment={},
                root_cause_diagnosis={},
                prescribed_action={},
                human_approval_required=False,
                governance_notes="Collector buffer empty. Seed synthetic load generator to simulate traffic rush.",
            )

        status_str = status_info.health_status.value
        headline = (
            f"PortalPulse Alert: {rca.primary_root_cause.value} Detected under {raw.requests_per_sec:,.0f} RPS Surge"
            if anomaly.is_anomaly
            else f"PortalPulse Operating Nominally: {raw.active_users:,.0f} Concurrent Users"
        )

        summary = (
            f"At {now_iso[:19]} UTC, PortalPulse evaluated platform telemetry across all 6 architectural tiers. "
            f"Operating status is {status_str}. Ingress traffic stands at {raw.requests_per_sec:,.0f} RPS with "
            f"average response time of {raw.response_time:.0f} ms and CPU utilization at {raw.cpu_percent:.1f}%. "
            f"The Multi-Horizon XGBoost forecaster projects safe capacity at {forecast.safe_capacity:,.0f} users. "
            f"The PyTorch Action Policy network recommends '{action.primary_action.value}' with {action.confidence * 100.0:.1f}% confidence."
        )

        return IncidentBrief(
            brief_id=brief_id,
            timestamp=now_iso,
            system_status=status_str,
            headline=headline,
            executive_summary=summary,
            key_metrics={
                "active_users": raw.active_users,
                "requests_per_sec": raw.requests_per_sec,
                "cpu_percent": raw.cpu_percent,
                "ram_percent": raw.ram_percent,
                "response_time_ms": raw.response_time,
                "error_rate": raw.error_rate,
                "db_latency_ms": raw.db_latency,
                "db_connections_percent": raw.db_connections,
                "queue_length": raw.queue_length,
                "service_instances": raw.service_instances,
            },
            projected_forecast_15m={
                "rps_5m": forecast.rps_5m,
                "cpu_5m": forecast.cpu_5m,
                "latency_5m": forecast.latency_5m,
                "rps_15m": forecast.rps_15m,
                "cpu_15m": forecast.cpu_15m,
                "safe_capacity": forecast.safe_capacity,
                "cpi": forecast.capacity_pressure_index,
                "risk_level": forecast.risk_level.value,
            },
            anomaly_assessment={
                "is_anomaly": anomaly.is_anomaly,
                "anomaly_score": anomaly.anomaly_score,
                "severity": anomaly.severity,
                "contributing_metrics": anomaly.contributing_metrics,
            },
            root_cause_diagnosis={
                "primary_root_cause": rca.primary_root_cause.value,
                "confidence": rca.confidence,
                "root_cause_tier": rca.root_cause_tier,
                "propagation_path": rca.causal_propagation_chain,
                "playbook": rca.recommended_mitigation,
            },
            prescribed_action={
                "action": action.primary_action.value,
                "confidence": action.confidence,
                "blast_radius": action.estimated_blast_radius,
                "rationale": action.tactical_rationale,
                "probabilities": action.all_action_probabilities,
            },
            human_approval_required=action.requires_human_approval,
            governance_notes=(
                "Mandatory Human-in-the-Loop approval enforced for actions exceeding LOW blast radius "
                "or sub-80% policy confidence pursuant to secure_action.md SRE policies."
            ),
        )


# Global singleton instance
COPILOT = SREOperationsCopilot()
