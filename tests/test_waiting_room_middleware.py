"""Unit tests for PortalPulse SDK Virtual Waiting Room, Dynamic Rate Limiter, and ASGI Middleware."""

import time
from fastapi import FastAPI
from fastapi.responses import JSONResponse, HTMLResponse
from starlette.testclient import TestClient

from portalpulse_sdk.middleware import (
    ActiveSessionTracker,
    DynamicRateLimiter,
    PortalPulseSessionMiddleware,
    VirtualWaitingRoom,
    render_waiting_room_html,
)


def test_dynamic_rate_limiter_basic():
    limiter = DynamicRateLimiter(default_rps=10.0, burst_multiplier=1.0)
    assert limiter.is_enabled()

    # Exhaust all tokens
    for _ in range(10):
        allowed, retry_after = limiter.allow_request()
        assert allowed

    # 11th request should be throttled
    allowed, retry_after = limiter.allow_request()
    assert not allowed
    assert retry_after > 0.0

    # Disabling rate limit allows requests freely
    limiter.set_rate_limit(None)
    assert not limiter.is_enabled()
    allowed, _ = limiter.allow_request()
    assert allowed


def test_virtual_waiting_room_fifo_queue():
    room = VirtualWaitingRoom(max_admitted_sessions=2, ticket_ttl_sec=10.0)
    room.enable(capacity=2)

    # First 2 users should be admitted immediately
    admitted1, pos1, wait1 = room.evaluate("user_1")
    assert admitted1
    assert pos1 == 0

    admitted2, pos2, wait2 = room.evaluate("user_2")
    assert admitted2
    assert pos2 == 0

    # 3rd and 4th users should be queued
    admitted3, pos3, wait3 = room.evaluate("user_3")
    assert not admitted3
    assert pos3 == 1
    assert wait3 > 0.0

    admitted4, pos4, wait4 = room.evaluate("user_4")
    assert not admitted4
    assert pos4 == 2
    assert wait4 >= wait3

    # Status inspection
    status = room.get_status()
    assert status["enabled"]
    assert status["max_admitted_sessions"] == 2
    assert status["currently_admitted"] == 2
    assert status["queue_length"] == 2

    # Prune with time jump to expire user_1 and user_2
    future_time = time.time() + 15.0
    room.prune_expired(now=future_time)

    # user_3 and user_4 should now be promoted from queue to admitted
    status_after = room.get_status()
    assert status_after["queue_length"] == 0
    assert status_after["currently_admitted"] == 2

    # Disable waiting room
    room.disable()
    assert not room.enabled
    admitted5, _, _ = room.evaluate("user_5")
    assert admitted5


def test_active_session_tracker_ux_metrics():
    tracker = ActiveSessionTracker()

    # Record some successful and failed requests
    tracker.record_request_finish(duration_ms=45.0, status_code=200, is_login=True)
    tracker.record_request_finish(duration_ms=55.0, status_code=200, is_login=True)
    tracker.record_request_finish(duration_ms=120.0, status_code=429, is_login=False)
    tracker.record_request_finish(duration_ms=350.0, status_code=500, is_login=False)

    metrics = tracker.get_ux_metrics()
    assert metrics["ux_login_success_rate"] == 100.0
    assert metrics["ux_429_rate"] == 25.0  # 1 out of 4 is 25%
    assert metrics["ux_5xx_rate"] == 25.0  # 1 out of 4 is 25%
    assert metrics["total_requests_recorded"] == 4


def test_asgi_middleware_waiting_room_and_exemptions():
    app = FastAPI()
    tracker = ActiveSessionTracker()
    app.add_middleware(PortalPulseSessionMiddleware, tracker=tracker)

    @app.get("/api/v1/protected/resource")
    def api_endpoint():
        return {"status": "ok", "data": "super_secret"}

    @app.get("/portal/browse")
    def portal_browse():
        return HTMLResponse("<h1>Welcome to Student Portal</h1>")

    @app.get("/health")
    def health_endpoint():
        return {"health": "alive"}

    client = TestClient(app)

    # Without waiting room, requests pass normally
    res1 = client.get("/api/v1/protected/resource")
    assert res1.status_code == 200
    assert res1.json() == {"status": "ok", "data": "super_secret"}

    # Enable waiting room with capacity = 1
    tracker.waiting_room.enable(capacity=1)

    # 1st user admitted: sets cookie pp_admitted=1
    client1 = TestClient(app)
    res_user1 = client1.get("/api/v1/protected/resource", headers={"x-session-id": "student_alpha"})
    assert res_user1.status_code == 200
    assert "pp_admitted=1" in res_user1.headers.get("set-cookie", "")

    # Subsequent request with admitted cookie passes through
    res_user1_retry = client1.get("/api/v1/protected/resource", headers={"x-session-id": "student_alpha"})
    assert res_user1_retry.status_code == 200

    # 2nd user exceeds capacity -> gets 429 JSON for API
    client2 = TestClient(app)
    res_user2 = client2.get(
        "/api/v1/protected/resource",
        headers={"x-session-id": "student_beta", "accept": "application/json"},
    )
    assert res_user2.status_code == 429
    assert res_user2.headers.get("x-portalpulse-waiting-room") == "1"
    body = res_user2.json()
    assert body["status"] == "WAITING_ROOM"
    assert body["queue_position"] >= 1

    # 3rd user exceeds capacity -> gets HTML Waiting Room for web browsing
    client3 = TestClient(app)
    res_user3 = client3.get(
        "/portal/browse",
        headers={"x-session-id": "student_gamma", "accept": "text/html"},
    )
    assert res_user3.status_code == 429
    assert "Virtual Waiting Room" in res_user3.text
    assert res_user3.headers.get("x-portalpulse-waiting-room") == "1"

    # Exempt paths like /health must NEVER be blocked by Waiting Room
    res_health = client3.get("/health")
    assert res_health.status_code == 200
    assert res_health.json() == {"health": "alive"}
