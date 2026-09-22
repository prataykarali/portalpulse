"""Automated Test Suite for Real Resource Discovery, Capacity Profiling, and Session Tracking.

Tests:
1. ResourceProfile and CapacityProfile validation & schema separation.
2. OS and Linux cgroups container resource discovery.
3. ActiveSessionTracker 3-tier identity hierarchy and 30s sliding window expiry.
4. In-flight concurrent request tracking and empirical latency reservoir (p50/p95/p99).
5. Nullable telemetry defaults (zero fabricated data).
6. Control Plane REST endpoints for resources, capacity profile, baseline, and sessions.
7. Out-of-process load benchmark subprocess manager.
"""

from __future__ import annotations

import time
from fastapi.testclient import TestClient

from backend.app import app
from backend.control_plane.baseline import BASELINE_ENGINE, PortalBaseline
from backend.simulation.process_manager import BENCHMARK_PROCESS_MANAGER
from portalpulse_sdk.discovery import detect_cgroup_limits, discover_resource_envelope
from portalpulse_sdk.middleware import ActiveSessionTracker, GLOBAL_SESSION_TRACKER
from portalpulse_sdk.schema import CapacityProfile, ResourceProfile, UniversalTelemetry

client = TestClient(app)


class TestResourceAndCapacitySchemas:
    """Validate strict separation between ResourceProfile and CapacityProfile."""

    def test_resource_profile_contains_pure_discovery_no_test_results(self) -> None:
        profile = ResourceProfile(
            portal_id="nirantar",
            host_cpu_cores=12,
            cpu_cores_physical=8,
            effective_cpu_limit=4.0,
            host_ram_mb=16384.0,
            effective_ram_limit_mb=8192.0,
            worker_count=8,
            worker_concurrency=32,
            db_pool_size=150,
            db_connection_limit=200,
            service_instances=8,
        )
        data = profile.model_dump()
        assert data["host_cpu_cores"] == 12
        assert data["effective_cpu_limit"] == 4.0
        assert data["effective_ram_limit_mb"] == 8192.0
        # Verify test results are NOT present in ResourceProfile
        assert "sustainable_rps" not in data
        assert "saturation_rps" not in data
        assert "degradation_knee_rps" not in data

    def test_capacity_profile_contains_measured_performance(self) -> None:
        cap = CapacityProfile(
            portal_id="nirantar",
            sustainable_rps=103.6,
            saturation_rps=164.6,
            sustainable_active_sessions=300,
            degradation_knee_rps=121.9,
            degradation_knee_vus=200,
            limiting_bottleneck="WORKER_CPU_SATURATION",
            p95_at_knee_ms=48.2,
            error_rate_at_saturation=0.045,
        )
        data = cap.model_dump()
        assert data["sustainable_rps"] == 103.6
        assert data["degradation_knee_vus"] == 200
        assert data["limiting_bottleneck"] == "WORKER_CPU_SATURATION"


class TestDiscoveryAndCgroups:
    """Test OS and cgroups inspection."""

    def test_cgroup_detection_runs_cleanly(self) -> None:
        version, eff_cpu, eff_ram = detect_cgroup_limits()
        # On this Linux environment or container, version can be v1, v2, or None
        assert version in (None, "v1", "v2")
        if eff_cpu is not None:
            assert eff_cpu > 0
        if eff_ram is not None:
            assert eff_ram > 0

    def test_discover_resource_envelope(self) -> None:
        env = discover_resource_envelope(
            portal_id="college_portal",
            worker_count=4,
            worker_concurrency=16,
            db_pool_size=40,
            db_connection_limit=50,
            service_instances=4,
        )
        assert env.portal_id == "college_portal"
        assert env.host_cpu_cores >= 1
        assert env.host_ram_mb > 0
        assert env.worker_count == 4
        assert env.db_pool_size == 40
        assert env.db_connection_limit == 50


class TestSessionTrackingHierarchyAndInFlight:
    """Test session identification hierarchy and concurrency accounting."""

    def test_session_hierarchy_tier_1_authenticated(self) -> None:
        tracker = ActiveSessionTracker()
        # X-Session-ID header
        sid, tier = tracker.extract_session_identity(
            headers={"x-session-id": "app_user_secret_token_123"},
            cookies={},
        )
        assert tier == "authenticated_token"
        assert sid.startswith("sess_auth_")
        assert "app_user_secret_token_123" not in sid  # Verify privacy hashing

        # Authorization Bearer header
        sid2, tier2 = tracker.extract_session_identity(
            headers={"authorization": "Bearer oauth2_access_key_999"},
            cookies={},
        )
        assert tier2 == "authenticated_token"

        # sessionid cookie
        sid3, tier3 = tracker.extract_session_identity(
            headers={},
            cookies={"sessionid": "django_sess_abc123"},
        )
        assert tier3 == "authenticated_cookie"

    def test_session_hierarchy_tier_2_anonymous_cookie(self) -> None:
        tracker = ActiveSessionTracker()
        sid, tier = tracker.extract_session_identity(
            headers={},
            cookies={"pp_anon_sid": "anon_cookie_val_456"},
        )
        assert tier == "anonymous_cookie"
        assert sid.startswith("sess_anon_")

    def test_session_hierarchy_tier_3_fallback_hash(self) -> None:
        tracker = ActiveSessionTracker()
        sid, tier = tracker.extract_session_identity(
            headers={},
            cookies={},
            client_ip="192.168.1.50",
            user_agent="Mozilla/5.0 TestAgent",
        )
        assert tier == "client_hash_fallback"
        assert sid.startswith("sess_client_")

    def test_sliding_window_session_expiry(self) -> None:
        tracker = ActiveSessionTracker(inactivity_window_sec=0.2)
        tracker.record_activity("sess_1", "authenticated_token")
        tracker.record_activity("sess_2", "anonymous_cookie")
        assert tracker.get_active_sessions() == 2

        # Sleep past inactivity window
        time.sleep(0.3)
        assert tracker.get_active_sessions() == 0

    def test_in_flight_concurrent_request_counting(self) -> None:
        tracker = ActiveSessionTracker()
        assert tracker.get_in_flight_requests() == 0

        tracker.record_request_start()
        tracker.record_request_start()
        assert tracker.get_in_flight_requests() == 2

        tracker.record_request_finish(12.5)
        assert tracker.get_in_flight_requests() == 1

        tracker.record_request_finish(18.2)
        assert tracker.get_in_flight_requests() == 0

    def test_latency_reservoir_percentiles(self) -> None:
        tracker = ActiveSessionTracker()
        # Empty reservoir returns None (no fake defaults!)
        p50, p95, p99 = tracker.get_latency_percentiles()
        assert p50 is None
        assert p95 is None
        assert p99 is None

        # Add 100 sample latencies: 1ms to 100ms
        for i in range(1, 101):
            tracker.record_request_finish(float(i))

        p50, p95, p99 = tracker.get_latency_percentiles()
        assert p50 == 51.0
        assert p95 == 96.0
        assert p99 == 100.0


class TestTelemetryHonesty:
    """Ensure unmeasured metrics return None rather than fake fabricated defaults."""

    def test_telemetry_defaults_to_none_when_unmeasured(self) -> None:
        tel = UniversalTelemetry(
            portal_id="test_portal",
            active_users=0,
            requests_per_sec=0.0,
            cpu_percent=5.0,
            ram_percent=20.0,
            latency_ms=2.0,
            throughput=0.0,
            error_rate=0.0,
        )
        assert tel.active_sessions is None
        assert tel.concurrent_requests is None
        assert tel.p50_latency_ms is None
        assert tel.p95_latency_ms is None
        assert tel.p99_latency_ms is None
        assert tel.memory_used_mb is None
        assert tel.memory_limit_mb is None


class TestEndpointsAndSubprocessManager:
    """Test REST endpoints and out-of-process benchmark manager."""

    def test_get_portal_resources_endpoint(self) -> None:
        resp = client.get("/api/v1/portals/nirantar/resources")
        assert resp.status_code == 200
        data = resp.json()
        assert data["portal_id"] == "nirantar"
        assert data["host_cpu_cores"] >= 1
        assert data["worker_count"] >= 8
        assert data["db_pool_size"] == 150

    def test_get_portal_capacity_profile_endpoint(self) -> None:
        resp = client.get("/api/v1/portals/nirantar/capacity-profile")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        assert data["portal_id"] == "nirantar"

    def test_get_portal_baseline_endpoint(self) -> None:
        resp = client.get("/api/v1/portals/nirantar/baseline")
        assert resp.status_code == 200
        data = resp.json()
        assert data["portal_id"] == "nirantar"
        assert data["baseline_p95_latency_ms"] > 0
        assert data["warning_p95_latency_ms"] > data["baseline_p95_latency_ms"]

    def test_get_portal_sessions_endpoint(self) -> None:
        resp = client.get("/api/v1/portals/nirantar/sessions")
        assert resp.status_code == 200
        data = resp.json()
        assert "active_sessions" in data
        assert "in_flight_requests" in data
        assert "session_identity_breakdown" in data

    def test_capacity_benchmark_lifecycle(self) -> None:
        # Start benchmark
        start_resp = client.post(
            "/api/v1/capacity-benchmark/start",
            json={
                "portal_id": "nirantar",
                "target_url": "http://127.0.0.1:8000",
                "ramp_steps": "50,100",
                "step_duration": 2.0,
            },
        )
        assert start_resp.status_code == 200
        start_data = start_resp.json()
        assert start_data["status"] == "STARTED"
        assert "pid" in start_data

        # Poll status
        status_resp = client.get("/api/v1/capacity-benchmark/status?portal_id=nirantar")
        assert status_resp.status_code == 200
        st = status_resp.json()
        assert "is_running" in st

        # Stop benchmark
        stop_resp = client.post(
            "/api/v1/capacity-benchmark/stop",
            json={"portal_id": "nirantar"},
        )
        assert stop_resp.status_code == 200
