"""S69: request-latency log lines + an in-memory percentile window.

Pure ASGI middleware (same shape as S44 security_headers, not
BaseHTTPMiddleware): it wraps `send` to capture the response status and
times the full inner stack. WebSocket scopes pass through unmeasured —
the companion bridge holds sockets for hours and an "elapsed ms" there
measures uptime, not latency, which would poison the window.

What it ships:
- ONE INFO log line per http request:
      latency method=GET path=/api/status status=200 ms=4.2
  A crashed handler (exception escaped the app, so no response start was
  necessarily delivered) logs `status=error` — an honest marker beats a
  borrowed 500 the process may never have sent.
- A bounded sliding window: the newest WINDOW_SIZE durations live in a
  deque under a lock; `/api/status` reads percentiles off it via
  snapshot(). Restart-clears, exactly like the S15 rate limiters — one
  uvicorn worker on :8090 (scripts/keepalive.sh) makes process memory the
  honest store, no redis, no new deps.

Deliberate exclusions:
- /health is skipped entirely (not counted, not logged). The keepalive
  cron curls it forever; sub-millisecond health hits would crowd the
  window and pin p50 near zero while real traffic rotted unseen in p95.
- Percentiles use NEAREST-RANK (index = ceil(q*n)-1 over the sorted
  window). With hundreds of samples interpolation is theatre; nearest-rank
  reports a value a request actually took.

Logging: emitted on the "llmtuner.metrics" logger. Under uvicorn's default
config INFO records reach the same stream keepalive already tails, so the
runbook (S55) can grep `latency` with zero extra plumbing.
"""

import logging
import math
import threading
import time
from collections import deque

logger = logging.getLogger("llmtuner.metrics")

# Count-based sliding window: the newest N http durations, oldest evicted.
WINDOW_SIZE = 1000

# Never measured, never logged: the keepalive cron's own probe path.
EXEMPT_PATHS = {"/health"}

_latencies: deque[float] = deque(maxlen=WINDOW_SIZE)
_lock = threading.Lock()


def record(latency_ms: float) -> None:
    """Push one duration into the sliding window."""
    with _lock:
        _latencies.append(max(0.0, latency_ms))


def reset() -> None:
    """Empty the window (tests; also handy for a manual re-baseline)."""
    with _lock:
        _latencies.clear()


def percentile(sorted_values: list[float], q: float) -> float | None:
    """Nearest-rank percentile over a SORTED window; None when empty."""
    n = len(sorted_values)
    if n == 0:
        return None
    return sorted_values[max(0, math.ceil(q * n) - 1)]


def snapshot() -> dict:
    """The /api/status payload fragment: p50/p95 over the live window."""
    with _lock:
        values = sorted(_latencies)
    return {
        "samples": len(values),
        "window_size": WINDOW_SIZE,
        "p50_ms": percentile(values, 0.50),
        "p95_ms": percentile(values, 0.95),
    }


def sanitize_path(path: str) -> str:
    """Control chars (incl. newlines) become '?' — a crafted URL must never
    split one request into two log lines."""
    return "".join(ch if " " <= ch != "\x7f" else "?" for ch in path)


class RequestMetricsMiddleware:
    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope.get("path", "") in EXEMPT_PATHS:
            await self.app(scope, receive, send)
            return

        started = time.monotonic()
        status = None
        crashed = False

        async def send_with_status(message):
            nonlocal status
            if message["type"] == "http.response.start" and status is None:
                status = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, send_with_status)
        except Exception:
            crashed = True
            raise
        finally:
            elapsed_ms = (time.monotonic() - started) * 1000.0
            record(elapsed_ms)
            outcome = "error" if crashed else str(status if status is not None else 0)
            logger.info(
                "latency method=%s path=%s status=%s ms=%.1f",
                scope.get("method", "-"),
                sanitize_path(scope.get("path", "")),
                outcome,
                elapsed_ms,
            )


def register(app) -> None:
    """Add the middleware. Call LAST (after security_headers) so metrics is
    the outermost layer and times the full stack, including the S15 bind
    guard's 403s — a refused request still cost the server real time."""
    app.add_middleware(RequestMetricsMiddleware)
