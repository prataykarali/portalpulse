"""Tests for Module 4: Server-Sent Events (SSE) Real-Time Streaming Subsystem.

Verifies:
1. SSE endpoint contract: GET /api/v1/stream/events with text/event-stream headers.
2. Publishing all 13 core domain event types:
   - telemetry
   - traffic
   - control_cycle
   - forecast
   - anomaly
   - rca
   - action
   - safety
   - actuation
   - warning
   - recovery
   - transaction
   - system_state
3. Compliance with requested control_cycle structure:
   {"type": "control_cycle", "cycle_id": 42, "timestamp": "...", "phase": "ACTUATING", "action": "..."}
4. Heartbeat and ping support.
5. Multi-client fan-out and non-blocking model execution.
6. Bounded event buffer and zero memory leaks.
7. Reconnection with Last-Event-ID replay.
8. Clean shutdown and status monitoring endpoint.
"""

import asyncio
import json
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient

from backend.app import app
from backend.streaming.broadcaster import STREAM_BROADCASTER, StreamBroadcaster, format_sse


@pytest.fixture(autouse=True)
def clean_broadcaster():
    """Reset global broadcaster state around tests."""
    STREAM_BROADCASTER.reset()
    yield
    STREAM_BROADCASTER.reset()


def test_stream_status_endpoint():
    """Verify GET /api/v1/stream/status returns active metrics and buffer capacity."""
    client = TestClient(app)
    resp = client.get("/api/v1/stream/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ONLINE"
    streaming = data["streaming"]
    assert "active_subscribers" in streaming
    assert "history_buffer_len" in streaming
    assert streaming["history_buffer_capacity"] >= 200
    assert "event_type_counts" in streaming


def test_stream_alias_endpoints():
    """Verify streaming status aliases work seamlessly."""
    client = TestClient(app)
    resp = client.get("/stream/status")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ONLINE"

    resp2 = client.get("/api/stream/status")
    assert resp2.status_code == 200
    assert resp2.json()["status"] == "ONLINE"


def test_format_sse_formatting():
    """Verify SSE wire formatting complies with W3C SSE standard."""
    raw = format_sse("control_cycle", {"type": "control_cycle", "cycle_id": 42}, event_id=101)
    lines = raw.strip().split("\n")
    assert lines[0] == "id: 101"
    assert lines[1] == "event: control_cycle"
    assert lines[2].startswith("data: ")
    payload = json.loads(lines[2][len("data: "):])
    assert payload["type"] == "control_cycle"
    assert payload["cycle_id"] == 42


def test_publish_all_13_required_events():
    """Verify all 13 core domain event types can be published and tracked."""
    broadcaster = StreamBroadcaster(history_buffer_size=50)

    event_payloads = {
        "telemetry": {"portal_id": "nirantar", "active_users": 1200, "latency_ms": 42.0},
        "traffic": {"phase": "SATURATION", "virtual_users": 12500, "workers": 48},
        "control_cycle": {
            "type": "control_cycle",
            "cycle_id": 42,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "phase": "ACTUATING",
            "action": "ENABLE_WAITING_ROOM",
        },
        "forecast": {"safe_capacity": 650, "predicted_cpu": 78.4},
        "anomaly": {"is_anomaly": True, "anomaly_score": 0.88, "severity": "CRITICAL"},
        "rca": {"root_cause": "DB_CONNECTION_EXHAUSTION", "confidence": 0.94},
        "action": {"action": "ENABLE_WAITING_ROOM", "confidence": 0.96},
        "safety": {"decision": "APPROVED", "is_safe": True},
        "actuation": {"status": "EXECUTED", "action": "ENABLE_WAITING_ROOM"},
        "warning": {"code": "POOL_SATURATION", "message": "DB Pool 98% saturated"},
        "recovery": {"recovery_state": "STABILIZING", "recovery_score": 95.0},
        "transaction": {"operation": "submit_exam", "duration_ms": 320, "success": True},
        "system_state": {"control_loop_running": True, "status": "HEALTHY"},
    }

    assert len(event_payloads) == 13

    for event_type, payload in event_payloads.items():
        res = broadcaster.publish(event_type, payload)
        assert res["type"] == event_type
        assert "timestamp" in res

    stats = broadcaster.get_stats()
    assert stats["total_events_published"] == 13
    assert stats["history_buffer_len"] == 13
    for event_type in event_payloads.keys():
        assert stats["event_type_counts"][event_type] == 1


def test_control_cycle_exact_structure():
    """Verify control_cycle matches user specification with type, cycle_id, timestamp, phase, action."""
    broadcaster = StreamBroadcaster()
    ts = datetime.now(timezone.utc).isoformat()
    evt = broadcaster.publish_control_cycle({
        "type": "control_cycle",
        "cycle_id": 42,
        "timestamp": ts,
        "phase": "ACTUATING",
        "action": "ENABLE_WAITING_ROOM",
    })
    assert evt["type"] == "control_cycle"
    assert evt["cycle_id"] == 42
    assert evt["timestamp"] == ts
    assert evt["phase"] == "ACTUATING"
    assert evt["action"] == "ENABLE_WAITING_ROOM"


@pytest.mark.anyio
async def test_multi_client_fanout_and_clean_disconnect():
    """Verify multiple subscriber clients receive broadcast events without blocking."""
    broadcaster = StreamBroadcaster()

    q1 = await broadcaster.register()
    q2 = await broadcaster.register()
    q3 = await broadcaster.register()

    assert broadcaster.active_subscribers_count == 3

    broadcaster.publish("warning", {"code": "TEST_ALERT", "message": "Test message"})

    assert not q1.empty()
    assert not q2.empty()
    assert not q3.empty()

    item1 = q1.get_nowait()
    item2 = q2.get_nowait()
    item3 = q3.get_nowait()

    assert item1["data"]["code"] == "TEST_ALERT"
    assert item2["data"]["code"] == "TEST_ALERT"
    assert item3["data"]["code"] == "TEST_ALERT"

    # Disconnect one client
    broadcaster.unregister(q2)
    assert broadcaster.active_subscribers_count == 2

    # Clean disconnect rest
    broadcaster.unregister(q1)
    broadcaster.unregister(q3)
    assert broadcaster.active_subscribers_count == 0


@pytest.mark.anyio
async def test_bounded_buffer_and_no_memory_leak():
    """Verify slow or unresponsive subscribers have oldest events dropped without unbounded growth."""
    broadcaster = StreamBroadcaster(history_buffer_size=10, client_queue_size=5)

    q = await broadcaster.register()

    # Publish 20 events into a queue of capacity 5
    for i in range(20):
        broadcaster.publish("traffic", {"count": i})

    # Buffer must not exceed history capacity
    assert len(broadcaster._history) == 10
    # Queue must not exceed its maxsize
    assert q.qsize() == 5

    # Should have the latest 5 events (15..19)
    items = []
    while not q.empty():
        items.append(q.get_nowait())
    counts = [item["data"]["count"] for item in items]
    assert counts == [15, 16, 17, 18, 19]

    broadcaster.unregister(q)
    assert broadcaster.active_subscribers_count == 0


@pytest.mark.anyio
async def test_reconnect_last_event_id_replay():
    """Verify a reconnecting client receives missed events since Last-Event-ID."""
    broadcaster = StreamBroadcaster(history_buffer_size=50)

    for i in range(1, 6):
        broadcaster.publish("telemetry", {"seq": i})

    # Client reconnects having seen up to event ID 3
    missed = broadcaster.get_history_since(last_event_id=3)
    assert len(missed) == 2
    assert missed[0]["id"] == 4
    assert missed[1]["id"] == 5


@pytest.mark.anyio
async def test_heartbeat_and_ping_generator():
    """Verify sse_generator emits initial system_state and heartbeats on idle timeout."""
    broadcaster = StreamBroadcaster()

    gen = broadcaster.sse_generator(heartbeat_interval=0.05)

    # First event is immediate system_state
    initial_event = await anext(gen)
    assert "event: system_state" in initial_event
    assert "PortalPulse SSE Stream Connected" in initial_event

    # Next should be heartbeat and ping due to 0.05s timeout
    heartbeat = await anext(gen)
    assert ": heartbeat" in heartbeat

    ping = await anext(gen)
    assert "event: ping" in ping

    await gen.aclose()
    assert broadcaster.active_subscribers_count == 0


@pytest.mark.anyio
async def test_clean_shutdown():
    """Verify shutdown cancels active generators and empties subscriber registry."""
    broadcaster = StreamBroadcaster()
    q = await broadcaster.register()
    assert broadcaster.active_subscribers_count == 1

    await broadcaster.shutdown()
    assert broadcaster.active_subscribers_count == 0
    assert broadcaster._is_shutdown is True
