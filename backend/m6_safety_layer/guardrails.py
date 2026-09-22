"""Deterministic Safety Rules Engine, Token Bucket, Circuit Breaker, and HITL Store.

Strict zero-ML execution gate enforcing operational constraints codified in secure_action.md:
- Minimum confidence threshold >= 80% (0.80)
- 5-minute (300s) flapping cooldown between identical actions
- Mandatory Human-in-the-Loop approval for HIGH blast radius actions
- Hard pod replica bounds [2, 24]
- Token bucket ingress rate limiting and Circuit Breaker tripping
"""

from __future__ import annotations

import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

from backend.m4_action_intelligence.schema import (
    ACTION_BLAST_RADIUS,
    SREAction,
)
from backend.m6_safety_layer.schema import (
    ActionIntent,
    ApprovalDecisionResponse,
    ApprovalRequest,
    ApprovalStatus,
    CircuitBreakerStatusResponse,
    CircuitState,
    SafetyValidationResult,
)

MIN_CONFIDENCE_THRESHOLD = 0.80
ACTION_COOLDOWN_SECONDS = 300.0  # 5 minutes
APPROVAL_TTL_SECONDS = 300.0  # 5 minutes
MIN_WORKER_PODS = 2
MAX_WORKER_PODS = 24


class TokenBucket:
    """Thread-safe Token Bucket Rate Limiter."""

    def __init__(self, capacity: float = 1000.0, refill_rate: float = 200.0) -> None:
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.tokens = capacity
        self.last_refill = time.monotonic()
        self.lock = threading.Lock()

    def consume(self, tokens: float = 1.0) -> bool:
        """Attempt to consume tokens. Returns True if permitted, False if throttled."""
        with self.lock:
            now = time.monotonic()
            elapsed = now - self.last_refill
            self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
            self.last_refill = now

            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False

    def get_status(self) -> Tuple[float, float, float]:
        """Return (available_tokens, capacity, refill_rate)."""
        with self.lock:
            now = time.monotonic()
            elapsed = now - self.last_refill
            tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
            return round(tokens, 2), self.capacity, self.refill_rate


class CircuitBreaker:
    """Circuit Breaker implementing Closed, Open, and Half-Open failure isolation."""

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout_sec: float = 30.0,
        error_rate_threshold: float = 0.08,
    ) -> None:
        self.failure_threshold = failure_threshold
        self.recovery_timeout_sec = recovery_timeout_sec
        self.error_rate_threshold = error_rate_threshold
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_state_change = time.monotonic()
        self.recent_error_rate = 0.0
        self.lock = threading.Lock()

    def record_outcome(self, error_rate: float, http_5xx: float) -> CircuitState:
        """Update circuit breaker state based on live error observations."""
        with self.lock:
            self.recent_error_rate = error_rate
            now = time.monotonic()

            if self.state == CircuitState.OPEN:
                if (now - self.last_state_change) >= self.recovery_timeout_sec:
                    self.state = CircuitState.HALF_OPEN
                    self.last_state_change = now

            elif self.state == CircuitState.CLOSED:
                if error_rate >= self.error_rate_threshold or http_5xx >= 100.0:
                    self.failure_count += 1
                    if self.failure_count >= self.failure_threshold:
                        self.state = CircuitState.OPEN
                        self.last_state_change = now
                else:
                    self.failure_count = max(0, self.failure_count - 1)

            elif self.state == CircuitState.HALF_OPEN:
                if error_rate < self.error_rate_threshold:
                    self.state = CircuitState.CLOSED
                    self.failure_count = 0
                    self.last_state_change = now
                else:
                    self.state = CircuitState.OPEN
                    self.last_state_change = now

            return self.state


class DeterministicSafetyGuardrails:
    """Zero-ML production safety engine and 2-phase human-in-the-loop approval coordinator."""

    def __init__(self) -> None:
        self.token_bucket = TokenBucket(capacity=1000.0, refill_rate=200.0)
        self.circuit_breaker = CircuitBreaker(failure_threshold=5, recovery_timeout_sec=30.0)
        self.last_executed_time: Dict[SREAction, float] = {}
        self.pending_approvals: Dict[str, ApprovalRequest] = {}
        self.lock = threading.Lock()

    def validate_action(
        self,
        intent: ActionIntent,
        current_replicas: int = 4,
        force_bypass_cooldown: bool = False,
    ) -> SafetyValidationResult:
        """Validate proposed SRE action against hard deterministic rules.

        Returns:
            SafetyValidationResult with approval requirement, rejection reasons, and cooldown state.
        """
        now = time.monotonic()
        rejections: List[str] = []
        requires_human = False
        action = intent.action
        confidence = intent.confidence
        blast_radius = ACTION_BLAST_RADIUS.get(action, "LOW")

        # 1. Nominal NO_OP: Always permitted without human approval
        if action == SREAction.NO_OP:
            return SafetyValidationResult(
                is_safe=True,
                requires_human_approval=False,
                rejection_reasons=[],
                blast_radius="NONE",
                cooldown_remaining_sec=0.0,
                approval_request_id=None,
                circuit_state=self.circuit_breaker.state,
                rate_limit_available=True,
            )

        # 2. Flapping Cooldown Check (5-minute cooldown)
        cooldown_remaining = 0.0
        with self.lock:
            last_time = self.last_executed_time.get(action)
            if last_time and not force_bypass_cooldown:
                elapsed = now - last_time
                if elapsed < ACTION_COOLDOWN_SECONDS:
                    cooldown_remaining = round(ACTION_COOLDOWN_SECONDS - elapsed, 1)
                    rejections.append(
                        f"Action '{action.value}' is in flapping cooldown ({cooldown_remaining}s remaining of 300s)."
                    )

        # 3. Resource Bounds Enforcement
        if action == SREAction.SCALE_OUT_WORKERS:
            requested_target = intent.parameters.get("target_replicas", current_replicas + 2)
            if requested_target > MAX_WORKER_PODS:
                rejections.append(
                    f"Scale-out target {requested_target} exceeds maximum cluster ceiling of {MAX_WORKER_PODS} pods."
                )

        elif action == SREAction.SCALE_IN_WORKERS:
            requested_target = intent.parameters.get("target_replicas", current_replicas - 2)
            if requested_target < MIN_WORKER_PODS:
                rejections.append(
                    f"Scale-in target {requested_target} breaches minimum cluster floor of {MIN_WORKER_PODS} pods."
                )

        # 4. Human Approval Enforcement Rules (secure_action.md)
        # Condition A: Confidence < 80% (0.80)
        if confidence < MIN_CONFIDENCE_THRESHOLD:
            requires_human = True

        # Condition B: Blast Radius is HIGH
        if blast_radius == "HIGH":
            requires_human = True

        # Condition C: Rate limiting requires validation if token bucket starved
        bucket_ok = self.token_bucket.consume(tokens=1.0)
        if not bucket_ok:
            rejections.append("Ingress token bucket exhausted; dynamic rate limiting throttled.")

        # Create approval request if human sign-off is needed and no hard bounds broken
        approval_id: Optional[str] = None
        is_safe = len(rejections) == 0

        if is_safe and requires_human:
            approval_id = self._create_approval_request(intent, blast_radius)

        return SafetyValidationResult(
            is_safe=is_safe,
            requires_human_approval=requires_human,
            rejection_reasons=rejections,
            blast_radius=blast_radius,
            cooldown_remaining_sec=cooldown_remaining,
            approval_request_id=approval_id,
            circuit_state=self.circuit_breaker.state,
            rate_limit_available=bucket_ok,
        )

    def _create_approval_request(self, intent: ActionIntent, blast_radius: str) -> str:
        """Create and register a pending human-in-the-loop approval ticket."""
        req_id = f"appr_{uuid.uuid4().hex[:8]}"
        now_dt = datetime.now(timezone.utc)
        expires_dt = now_dt + timedelta(seconds=APPROVAL_TTL_SECONDS)

        req = ApprovalRequest(
            request_id=req_id,
            action=intent.action,
            confidence=intent.confidence,
            blast_radius=blast_radius,
            justification=intent.justification or f"Automated recommendation for {intent.action.value}",
            parameters=intent.parameters,
            requested_at=now_dt.isoformat(),
            expires_at=expires_dt.isoformat(),
            status=ApprovalStatus.PENDING,
        )

        with self.lock:
            self._cleanup_expired_approvals()
            self.pending_approvals[req_id] = req

        return req_id

    def decide_approval(
        self,
        request_id: str,
        approved: bool,
        operator_id: str,
        comment: str,
    ) -> ApprovalDecisionResponse:
        """Record operator human approval or rejection of a pending SRE action."""
        now_iso = datetime.now(timezone.utc).isoformat()
        with self.lock:
            self._cleanup_expired_approvals()
            req = self.pending_approvals.get(request_id)
            if not req:
                raise KeyError(f"Approval request '{request_id}' not found or has expired.")

            if req.status != ApprovalStatus.PENDING:
                return ApprovalDecisionResponse(
                    request_id=request_id,
                    status=req.status,
                    message=f"Request already transitioned to {req.status.value}",
                    operator_id=req.operator_id or operator_id,
                    decided_at=req.decided_at or now_iso,
                )

            req.status = ApprovalStatus.APPROVED if approved else ApprovalStatus.REJECTED
            req.operator_id = operator_id
            req.decision_comment = comment
            req.decided_at = now_iso

            # If approved, register timestamp for flapping cooldown
            if approved:
                self.last_executed_time[req.action] = time.monotonic()

            decision_msg = (
                f"Operator '{operator_id}' APPROVED action '{req.action.value}' for immediate execution."
                if approved
                else f"Operator '{operator_id}' REJECTED action '{req.action.value}'."
            )

            return ApprovalDecisionResponse(
                request_id=request_id,
                status=req.status,
                message=decision_msg,
                operator_id=operator_id,
                decided_at=now_iso,
            )

    def record_action_executed(self, action: SREAction) -> None:
        """Mark an action as executed to begin flapping cooldown."""
        with self.lock:
            self.last_executed_time[action] = time.monotonic()

    def get_pending_approvals(self) -> List[ApprovalRequest]:
        """Retrieve all currently active pending approval requests."""
        with self.lock:
            self._cleanup_expired_approvals()
            return [req for req in self.pending_approvals.values() if req.status == ApprovalStatus.PENDING]

    def _cleanup_expired_approvals(self) -> None:
        """Mark stale approval tickets older than 5 minutes as EXPIRED."""
        now_dt = datetime.now(timezone.utc)
        for req in list(self.pending_approvals.values()):
            if req.status == ApprovalStatus.PENDING:
                exp = datetime.fromisoformat(req.expires_at)
                if now_dt >= exp:
                    req.status = ApprovalStatus.EXPIRED

    def get_circuit_breaker_status(self) -> CircuitBreakerStatusResponse:
        """Return circuit breaker and token bucket health status."""
        avail, cap, ref = self.token_bucket.get_status()
        return CircuitBreakerStatusResponse(
            state=self.circuit_breaker.state,
            failure_count=self.circuit_breaker.failure_count,
            failure_threshold=self.circuit_breaker.failure_threshold,
            error_rate_window=self.circuit_breaker.recent_error_rate,
            recovery_timeout_sec=self.circuit_breaker.recovery_timeout_sec,
            token_bucket_available=avail,
            token_bucket_capacity=cap,
            token_bucket_refill_rate=ref,
        )


# Global singleton instance
SAFETY_GUARDRAILS = DeterministicSafetyGuardrails()
