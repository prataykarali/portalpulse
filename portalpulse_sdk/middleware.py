"""Active Session & In-Flight Concurrency Tracking Middleware for PortalPulse SDK.

Strictly differentiates:
1. Active Sessions: Human/client sessions active within a sliding 30-second window.
   Identity hierarchy: Authenticated Token -> Anonymous Cookie -> Anonymized Fallback.
2. In-Flight Requests: HTTP transactions currently being processed on the server.
3. Requests Per Second (RPS): Arrival throughput rate.
4. Latency Percentiles: Rolling reservoir measuring actual empirical P50, P95, and P99.
5. Virtual Waiting Room: Token-bucket concurrency gating with FIFO queue & UX metrics.
6. Dynamic Rate Limiter: Token-bucket ingress throttling.
"""

from __future__ import annotations

import collections
import hashlib
import hmac
import json
import logging
import threading
import time
from typing import Any, Deque, Dict, List, Optional, Set, Tuple

logger = logging.getLogger("portalpulse.sdk.middleware")

# Secret salt for anonymous hashing (prevents rainbow table reversal)
_SESSION_SALT = b"portalpulse_session_anonymizer_salt_2026"


class DynamicRateLimiter:
    """Thread-safe token bucket rate limiter for ingress traffic throttling."""

    def __init__(self, default_rps: Optional[float] = None, burst_multiplier: float = 1.5) -> None:
        self.lock = threading.Lock()
        self.rate_limit_rps: Optional[float] = default_rps
        self.burst_multiplier = burst_multiplier
        self.tokens: float = float(default_rps or 1000.0)
        self.last_refill: float = time.perf_counter()

    def set_rate_limit(self, rps: Optional[float]) -> None:
        """Dynamically update rate limit threshold (None to disable)."""
        with self.lock:
            self.rate_limit_rps = rps
            if rps is not None and rps > 0:
                self.tokens = min(self.tokens, rps * self.burst_multiplier)

    def is_enabled(self) -> bool:
        with self.lock:
            return self.rate_limit_rps is not None and self.rate_limit_rps > 0

    def allow_request(self) -> Tuple[bool, float]:
        """Check if request is allowed under current rate limit.

        Returns:
            (allowed, retry_after_sec)
        """
        with self.lock:
            if self.rate_limit_rps is None or self.rate_limit_rps <= 0:
                return True, 0.0

            now = time.perf_counter()
            elapsed = now - self.last_refill
            self.last_refill = now
            capacity = self.rate_limit_rps * self.burst_multiplier
            self.tokens = min(capacity, self.tokens + (elapsed * self.rate_limit_rps))

            if self.tokens >= 1.0:
                self.tokens -= 1.0
                return True, 0.0
            else:
                retry_after = round(max(0.1, (1.0 - self.tokens) / self.rate_limit_rps), 2)
                return False, retry_after


class VirtualWaitingRoom:
    """Active Token-Bucket Virtual Waiting Room.

    Protects backend databases and application workers from stampede crashes
    by gating concurrent active sessions. Sessions exceeding the configured
    capacity are placed in an orderly FIFO queue and presented with a waiting
    room interface or HTTP 429 status with estimated wait duration.
    """

    def __init__(
        self,
        max_admitted_sessions: int = 500,
        ticket_ttl_sec: float = 300.0,
        poll_interval_sec: int = 5,
    ) -> None:
        self.lock = threading.Lock()
        self.enabled: bool = False
        self.max_admitted_sessions: int = max_admitted_sessions
        self.ticket_ttl_sec: float = ticket_ttl_sec
        self.poll_interval_sec: int = poll_interval_sec
        # session_hash -> admission_timestamp
        self._admitted: Dict[str, float] = {}
        # session_hash -> queue_join_timestamp (OrderedDict preserves arrival order)
        self._queue: collections.OrderedDict[str, float] = collections.OrderedDict()
        # Historical queue wait durations for UX metrics
        self._wait_durations: Deque[float] = collections.deque(maxlen=1000)

    def enable(self, capacity: Optional[int] = None) -> None:
        """Activate the virtual waiting room with given concurrency capacity."""
        with self.lock:
            self.enabled = True
            if capacity is not None and capacity > 0:
                self.max_admitted_sessions = capacity

    def disable(self) -> None:
        """Deactivate waiting room, automatically admitting queued sessions."""
        with self.lock:
            self.enabled = False
            now = time.time()
            for sid, join_time in list(self._queue.items()):
                self._admitted[sid] = now
                self._wait_durations.append(now - join_time)
            self._queue.clear()

    def prune_expired(self, now: Optional[float] = None) -> None:
        """Evict expired admissions and promote next in queue."""
        curr = now or time.time()
        # Evict expired admitted sessions
        expired = [sid for sid, adm_time in self._admitted.items() if (curr - adm_time) > self.ticket_ttl_sec]
        for sid in expired:
            del self._admitted[sid]

        # Evict stale queued sessions (queued > 15 mins without polling)
        stale = [sid for sid, join_time in self._queue.items() if (curr - join_time) > 900.0]
        for sid in stale:
            del self._queue[sid]

        # Promote from queue if capacity freed
        available_slots = max(0, self.max_admitted_sessions - len(self._admitted))
        while available_slots > 0 and self._queue:
            next_sid, join_time = self._queue.popitem(last=False)
            self._admitted[next_sid] = curr
            self._wait_durations.append(curr - join_time)
            available_slots -= 1

    def evaluate(self, session_hash: str) -> Tuple[bool, int, float]:
        """Evaluate session against waiting room policy.

        Returns:
            (is_admitted, queue_position, estimated_wait_seconds)
            If is_admitted is True, queue_position is 0 and wait is 0.0.
        """
        with self.lock:
            if not self.enabled:
                return True, 0, 0.0

            now = time.time()
            self.prune_expired(now)

            # Already admitted with active pass
            if session_hash in self._admitted:
                return True, 0, 0.0

            # Capacity available -> admit immediately
            if len(self._admitted) < self.max_admitted_sessions:
                if session_hash in self._queue:
                    join_time = self._queue.pop(session_hash)
                    self._wait_durations.append(now - join_time)
                self._admitted[session_hash] = now
                return True, 0, 0.0

            # Capacity exhausted -> place or maintain in queue
            if session_hash not in self._queue:
                self._queue[session_hash] = now

            queue_keys = list(self._queue.keys())
            try:
                pos = queue_keys.index(session_hash) + 1
            except ValueError:
                pos = len(queue_keys)

            turnover_rate = max(1.0, float(self.max_admitted_sessions)) / max(1.0, self.ticket_ttl_sec)
            est_wait = round(max(1.0, pos / turnover_rate), 1)

            return False, pos, est_wait

    def get_status(self) -> Dict[str, Any]:
        """Return real-time waiting room status and statistics."""
        with self.lock:
            self.prune_expired()
            avg_wait = (
                round(sum(self._wait_durations) / len(self._wait_durations), 1)
                if self._wait_durations
                else 0.0
            )
            return {
                "enabled": self.enabled,
                "max_admitted_sessions": self.max_admitted_sessions,
                "currently_admitted": len(self._admitted),
                "queue_length": len(self._queue),
                "avg_wait_time_sec": avg_wait,
                "ticket_ttl_sec": self.ticket_ttl_sec,
                "poll_interval_sec": self.poll_interval_sec,
            }


class ActiveSessionTracker:
    """Thread-safe sliding window session and in-flight request tracker with UX metrics."""

    def __init__(self, inactivity_window_sec: float = 30.0, reservoir_size: int = 2000) -> None:
        self.inactivity_window_sec = inactivity_window_sec
        self.lock = threading.Lock()
        # session_hash -> (last_seen_epoch, session_tier)
        self._sessions: Dict[str, Tuple[float, str]] = {}
        # In-flight concurrent request counter
        self._in_flight: int = 0
        # Latency reservoir (duration in ms)
        self._latencies: Deque[float] = collections.deque(maxlen=reservoir_size)
        # Request arrival timestamps for rolling RPS (last 5 seconds)
        self._arrival_times: Deque[float] = collections.deque(maxlen=5000)

        # Integrated Waiting Room and Rate Limiter
        self.waiting_room = VirtualWaitingRoom()
        self.rate_limiter = DynamicRateLimiter()

        # UX and response code tracking (last 2000 responses)
        # Each entry is (timestamp, status_code, is_login_or_critical)
        self._response_history: Deque[Tuple[float, int, bool]] = collections.deque(maxlen=2000)
        self._total_requests: int = 0
        self._total_429: int = 0
        self._total_5xx: int = 0

    def extract_session_identity(
        self,
        headers: Dict[str, str],
        cookies: Dict[str, str],
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Tuple[str, str]:
        """Resolve session identity following the 3-tier hierarchy."""
        # Tier 1: Explicit session token
        x_session = headers.get("x-session-id")
        if x_session:
            h = hmac.new(_SESSION_SALT, x_session.encode("utf-8"), hashlib.sha256).hexdigest()[:16]
            return f"sess_auth_{h}", "authenticated_token"

        auth_header = headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            raw_token = auth_header[7:].strip()
            h = hmac.new(_SESSION_SALT, raw_token.encode("utf-8"), hashlib.sha256).hexdigest()[:16]
            return f"sess_auth_{h}", "authenticated_token"

        cookie_sid = cookies.get("sessionid") or cookies.get("session_id") or cookies.get("token")
        if cookie_sid:
            h = hmac.new(_SESSION_SALT, cookie_sid.encode("utf-8"), hashlib.sha256).hexdigest()[:16]
            return f"sess_auth_{h}", "authenticated_cookie"

        # Tier 2: Anonymous session cookie
        anon_cookie = cookies.get("pp_anon_sid")
        if anon_cookie:
            h = hmac.new(_SESSION_SALT, anon_cookie.encode("utf-8"), hashlib.sha256).hexdigest()[:16]
            return f"sess_anon_{h}", "anonymous_cookie"

        # Tier 3: Anonymized client hash fallback
        combined = f"{client_ip or '127.0.0.1'}:{user_agent or 'unknown'}"
        h = hmac.new(_SESSION_SALT, combined.encode("utf-8"), hashlib.sha256).hexdigest()[:16]
        return f"sess_client_{h}", "client_hash_fallback"

    def record_activity(self, session_hash: str, session_tier: str) -> None:
        """Update last-seen timestamp for an active session."""
        now = time.time()
        with self.lock:
            self._sessions[session_hash] = (now, session_tier)

    def record_request_start(self) -> None:
        """Mark an in-flight request started and log arrival timestamp for RPS."""
        now = time.time()
        with self.lock:
            self._in_flight += 1
            self._arrival_times.append(now)

    def record_request_finish(
        self,
        duration_ms: float,
        status_code: int = 200,
        is_login: bool = False,
    ) -> None:
        """Mark an in-flight request completed and add duration to latency reservoir."""
        now = time.time()
        with self.lock:
            if self._in_flight > 0:
                self._in_flight -= 1
            self._latencies.append(duration_ms)
            self._response_history.append((now, status_code, is_login))
            self._total_requests += 1
            if status_code == 429:
                self._total_429 += 1
            elif status_code >= 500:
                self._total_5xx += 1

    def prune_expired_sessions(self, now: Optional[float] = None) -> None:
        """Remove sessions that have been idle past the inactivity window."""
        curr = now or time.time()
        cutoff = curr - self.inactivity_window_sec
        expired = [sid for sid, (last_seen, _) in self._sessions.items() if last_seen < cutoff]
        for sid in expired:
            del self._sessions[sid]

    def get_active_sessions(self) -> int:
        """Number of distinct sessions active within the last 30 seconds."""
        with self.lock:
            self.prune_expired_sessions()
            return len(self._sessions)

    def get_in_flight_requests(self) -> int:
        """Number of HTTP requests currently in flight on the host."""
        with self.lock:
            return self._in_flight

    def get_requests_per_second(self, window_sec: float = 2.0) -> float:
        """Calculate recent request arrival throughput (RPS)."""
        now = time.time()
        cutoff = now - window_sec
        with self.lock:
            while self._arrival_times and self._arrival_times[0] < (now - 5.0):
                self._arrival_times.popleft()

            recent = sum(1 for t in self._arrival_times if t >= cutoff)
            return round(recent / window_sec, 2)

    def get_latency_percentiles(self) -> Tuple[Optional[float], Optional[float], Optional[float]]:
        """Compute (p50, p95, p99) response latency in milliseconds from reservoir."""
        with self.lock:
            if not self._latencies:
                return None, None, None

            sorted_lat = sorted(self._latencies)
            n = len(sorted_lat)

            p50_idx = int(n * 0.50)
            p95_idx = min(int(n * 0.95), n - 1)
            p99_idx = min(int(n * 0.99), n - 1)

            return (
                round(sorted_lat[p50_idx], 2),
                round(sorted_lat[p95_idx], 2),
                round(sorted_lat[p99_idx], 2),
            )

    def get_session_breakdown(self) -> Dict[str, int]:
        """Return count of active sessions categorized by identity tier."""
        with self.lock:
            self.prune_expired_sessions()
            breakdown: Dict[str, int] = {
                "authenticated_token": 0,
                "authenticated_cookie": 0,
                "anonymous_cookie": 0,
                "client_hash_fallback": 0,
            }
            for _, (_, tier) in self._sessions.items():
                breakdown[tier] = breakdown.get(tier, 0) + 1
            return breakdown

    def get_ux_metrics(self) -> Dict[str, Any]:
        """Calculate live User Experience (UX) metrics."""
        with self.lock:
            now = time.time()
            cutoff = now - 60.0  # Last 60 seconds
            recent = [item for item in self._response_history if item[0] >= cutoff]

            total = len(recent)
            if total == 0:
                return {
                    "ux_login_success_rate": 100.0,
                    "ux_avg_wait_time_sec": self.waiting_room.get_status()["avg_wait_time_sec"],
                    "ux_429_rate": 0.0,
                    "ux_5xx_rate": 0.0,
                    "total_requests_recorded": self._total_requests,
                }

            login_reqs = [item for item in recent if item[2]]
            if login_reqs:
                successful_logins = sum(1 for item in login_reqs if item[1] < 400)
                login_success_pct = round((successful_logins / len(login_reqs)) * 100.0, 1)
            else:
                login_success_pct = 100.0

            rate_429 = round((sum(1 for item in recent if item[1] == 429) / total) * 100.0, 1)
            rate_5xx = round((sum(1 for item in recent if item[1] >= 500) / total) * 100.0, 1)

            return {
                "ux_login_success_rate": login_success_pct,
                "ux_avg_wait_time_sec": self.waiting_room.get_status()["avg_wait_time_sec"],
                "ux_429_rate": rate_429,
                "ux_5xx_rate": rate_5xx,
                "total_requests_recorded": self._total_requests,
            }

    def get_telemetry_dict(self) -> Dict[str, Any]:
        """Aggregate live telemetry metrics into a dictionary for adapters and observers."""
        p50, p95, p99 = self.get_latency_percentiles()
        wr_status = self.waiting_room.get_status()
        ux = self.get_ux_metrics()
        rps = self.get_requests_per_second()
        sessions = self.get_active_sessions()
        avg_lat = p50 or 12.0
        return {
            "active_sessions": sessions,
            "requests_per_sec": rps,
            "in_flight_requests": self.get_in_flight_requests(),
            "avg_latency_ms": avg_lat,
            "p50_latency_ms": p50 or avg_lat,
            "p95_latency_ms": p95 or round(avg_lat * 1.8, 1),
            "p99_latency_ms": p99 or round(avg_lat * 2.5, 1),
            "waiting_room_queue_size": wr_status.get("queue_length", 0),
            "waiting_room_admitted": wr_status.get("currently_admitted", 0),
            "rate_5xx_pct": ux.get("ux_5xx_rate", 0.0),
            "rate_429_pct": ux.get("ux_429_rate", 0.0),
            "login_success_pct": ux.get("ux_login_success_rate", 100.0),
            "avg_wait_time_sec": wr_status.get("avg_wait_time_sec", 0.0),
        }



# Global singleton tracker for application monitoring
GLOBAL_SESSION_TRACKER = ActiveSessionTracker()


def render_waiting_room_html(queue_position: int, est_wait_sec: float, poll_sec: int = 5) -> str:
    """Generate professional glassmorphism Waiting Room HTML interface."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta http-equiv="refresh" content="{poll_sec}">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>PortalPulse — Virtual Waiting Room</title>
  <style>
    :root {{
      --bg: #07090e;
      --card-bg: rgba(15, 23, 42, 0.85);
      --border: rgba(56, 189, 248, 0.25);
      --accent: #38bdf8;
      --accent-glow: rgba(56, 189, 248, 0.35);
      --text: #f8fafc;
      --text-muted: #94a3b8;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }}
    body {{
      background-color: var(--bg);
      background-image: radial-gradient(circle at 50% 20%, rgba(56, 189, 248, 0.1) 0%, transparent 60%);
      color: var(--text);
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 24px;
    }}
    .card {{
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 20px;
      padding: 40px;
      max-width: 520px;
      width: 100%;
      text-align: center;
      box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5), 0 0 40px var(--accent-glow);
      backdrop-filter: blur(16px);
    }}
    .badge {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 6px 14px;
      border-radius: 9999px;
      background: rgba(56, 189, 248, 0.12);
      border: 1px solid rgba(56, 189, 248, 0.3);
      color: var(--accent);
      font-size: 12px;
      font-weight: 600;
      letter-spacing: 0.05em;
      text-transform: uppercase;
      margin-bottom: 24px;
    }}
    .pulse-dot {{
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: var(--accent);
      box-shadow: 0 0 10px var(--accent);
      animation: pulse 1.5s infinite;
    }}
    @keyframes pulse {{
      0%, 100% {{ opacity: 1; transform: scale(1); }}
      50% {{ opacity: 0.4; transform: scale(0.85); }}
    }}
    h1 {{ font-size: 24px; font-weight: 700; margin-bottom: 12px; letter-spacing: -0.02em; }}
    p.desc {{ color: var(--text-muted); font-size: 14px; line-height: 1.6; margin-bottom: 32px; }}
    .queue-box {{
      background: rgba(2, 6, 23, 0.6);
      border: 1px solid rgba(255, 255, 255, 0.08);
      border-radius: 14px;
      padding: 24px;
      margin-bottom: 28px;
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 16px;
    }}
    .metric-title {{ font-size: 12px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 6px; }}
    .metric-value {{ font-size: 32px; font-weight: 800; color: #38bdf8; }}
    .radar {{
      width: 56px;
      height: 56px;
      margin: 0 auto 24px;
      border: 3px solid rgba(56, 189, 248, 0.2);
      border-top-color: var(--accent);
      border-radius: 50%;
      animation: spin 1s linear infinite;
    }}
    @keyframes spin {{ to {{ transform: rotate(360deg); }} }}
    .countdown {{ font-size: 13px; color: var(--text-muted); }}
    .countdown span {{ color: var(--accent); font-weight: 600; }}
  </style>
</head>
<body>
  <div class="card">
    <div class="badge"><span class="pulse-dot"></span> Surge Traffic Shield Active</div>
    <div class="radar"></div>
    <h1>Virtual Waiting Room</h1>
    <p class="desc">High surge traffic is currently being prioritized to protect system reliability. We have secured your place in line. Please keep this page open.</p>
    <div class="queue-box">
      <div>
        <div class="metric-title">Position in Queue</div>
        <div class="metric-value">#{queue_position}</div>
      </div>
      <div>
        <div class="metric-title">Estimated Wait</div>
        <div class="metric-value">~{est_wait_sec}s</div>
      </div>
    </div>
    <div class="countdown">Re-evaluating admission in <span id="timer">{poll_sec}</span>s...</div>
  </div>
  <script>
    let t = {poll_sec};
    const el = document.getElementById('timer');
    setInterval(() => {{
      t--;
      if (t <= 0) {{ window.location.reload(); }}
      else if (el) {{ el.innerText = t; }}
    }}, 1000);
  </script>
</body>
</html>"""


class PortalPulseSessionMiddleware:
    """ASGI middleware for Starlette / FastAPI applications.

    Tracks active sessions, in-flight concurrent requests, request latencies,
    and enforces Virtual Waiting Room & Dynamic Rate Limiting.
    """

    EXEMPT_EXACT = {
        "/",
        "/health",
        "/api/v1/health",
        "/favicon.ico",
        "/style.css",
        "/app.js",
        "/docs",
        "/redoc",
        "/openapi.json",
    }

    EXEMPT_PREFIXES = (
        "/static/",
        "/assets/",
        "/api/v1/control-plane/",
        "/api/v1/telemetry/",
        "/api/v1/actions/",
        "/api/v1/m1/",
        "/api/v1/m2/",
        "/api/v1/m3/",
        "/api/v1/m4/",
        "/api/v1/m5/",
        "/api/v1/m6/",
        "/api/v1/m7/",
        "/api/v1/m8/",
        "/api/v1/m9/",
        "/api/v1/simulation/",
    )

    def __init__(self, app: Any, tracker: Optional[ActiveSessionTracker] = None) -> None:
        self.app = app
        self.tracker = tracker or GLOBAL_SESSION_TRACKER

    async def __call__(self, scope: Dict[str, Any], receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "/")

        # Extract headers and cookies from ASGI scope
        headers_raw = dict(scope.get("headers", []))
        headers = {k.decode("latin1").lower(): v.decode("latin1") for k, v in headers_raw.items()}

        cookies_raw = headers.get("cookie", "")
        cookies: Dict[str, str] = {}
        if cookies_raw:
            for item in cookies_raw.split(";"):
                if "=" in item:
                    k, v = item.strip().split("=", 1)
                    cookies[k] = v

        client = scope.get("client")
        client_ip = client[0] if client else "127.0.0.1"
        user_agent = headers.get("user-agent", "")
        accept_header = headers.get("accept", "")
        is_api_request = path.startswith("/api/") or "application/json" in accept_header
        is_login = "login" in path.lower() or "auth" in path.lower()

        # 1. Resolve session identity
        session_hash, tier = self.tracker.extract_session_identity(
            headers=headers,
            cookies=cookies,
            client_ip=client_ip,
            user_agent=user_agent,
        )

        # 2. Record activity and request arrival
        self.tracker.record_activity(session_hash, tier)
        self.tracker.record_request_start()

        # Check if route is exempt from waiting room & rate limiter
        is_exempt = path in self.EXEMPT_EXACT or any(path.startswith(pre) for pre in self.EXEMPT_PREFIXES)

        start_time = time.perf_counter()
        status_code_container = [200]

        # 3. Dynamic Rate Limiter Enforcement (non-exempt paths)
        if not is_exempt and self.tracker.rate_limiter.is_enabled():
            allowed, retry_sec = self.tracker.rate_limiter.allow_request()
            if not allowed:
                duration_ms = (time.perf_counter() - start_time) * 1000.0
                self.tracker.record_request_finish(duration_ms, status_code=429, is_login=is_login)
                err_payload = json.dumps({
                    "error": "rate_limit_exceeded",
                    "message": f"Too many requests. Please retry in {retry_sec} seconds.",
                    "retry_after": retry_sec,
                }).encode("utf-8")
                await send({
                    "type": "http.response.start",
                    "status": 429,
                    "headers": [
                        (b"content-type", b"application/json"),
                        (b"retry-after", str(int(max(1, retry_sec))).encode("latin1")),
                        (b"x-portalpulse-throttled", b"1"),
                    ],
                })
                await send({"type": "http.response.body", "body": err_payload})
                return

        # 4. Virtual Waiting Room Enforcement (non-exempt paths)
        if not is_exempt and self.tracker.waiting_room.enabled:
            # Check if user already holds a valid admission cookie
            has_admit_cookie = cookies.get("pp_admitted") == "1"
            if not has_admit_cookie:
                admitted, queue_pos, wait_sec = self.tracker.waiting_room.evaluate(session_hash)
                if not admitted:
                    duration_ms = (time.perf_counter() - start_time) * 1000.0
                    self.tracker.record_request_finish(duration_ms, status_code=429, is_login=is_login)

                    if is_api_request:
                        body_data = json.dumps({
                            "status": "WAITING_ROOM",
                            "message": "PortalPulse Virtual Waiting Room active. System operating at capacity.",
                            "queue_position": queue_pos,
                            "estimated_wait_seconds": wait_sec,
                            "retry_after": 5,
                        }).encode("utf-8")
                        await send({
                            "type": "http.response.start",
                            "status": 429,
                            "headers": [
                                (b"content-type", b"application/json"),
                                (b"retry-after", b"5"),
                                (b"x-portalpulse-waiting-room", b"1"),
                                (b"x-queue-position", str(queue_pos).encode("latin1")),
                            ],
                        })
                        await send({"type": "http.response.body", "body": body_data})
                    else:
                        html_body = render_waiting_room_html(
                            queue_position=queue_pos,
                            est_wait_sec=wait_sec,
                            poll_sec=5,
                        ).encode("utf-8")
                        await send({
                            "type": "http.response.start",
                            "status": 429,
                            "headers": [
                                (b"content-type", b"text/html; charset=utf-8"),
                                (b"retry-after", b"5"),
                                (b"x-portalpulse-waiting-room", b"1"),
                                (b"x-queue-position", str(queue_pos).encode("latin1")),
                            ],
                        })
                        await send({"type": "http.response.body", "body": html_body})
                    return

        # 5. Admitted/Allowed Execution
        async def send_wrapper(message: Dict[str, Any]) -> None:
            if message["type"] == "http.response.start":
                status_code_container[0] = message.get("status", 200)
                headers_list = list(message.get("headers", []))

                # Inject anonymous cookie if client had no existing identifier
                if tier == "client_hash_fallback" and "pp_anon_sid" not in cookies:
                    headers_list.append((
                        b"set-cookie",
                        f"pp_anon_sid={session_hash}; Path=/; HttpOnly; SameSite=Lax".encode("latin1"),
                    ))

                # If waiting room is active and user is admitted, set admission cookie
                if self.tracker.waiting_room.enabled and cookies.get("pp_admitted") != "1":
                    headers_list.append((
                        b"set-cookie",
                        b"pp_admitted=1; Path=/; Max-Age=300; SameSite=Lax",
                    ))

                message["headers"] = headers_list
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            self.tracker.record_request_finish(
                duration_ms,
                status_code=status_code_container[0],
                is_login=is_login,
            )
