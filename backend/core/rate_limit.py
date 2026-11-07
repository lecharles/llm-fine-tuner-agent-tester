"""S15 (#17): tiny in-process sliding-window rate limiter.

Scope is deliberately small: today the only throttled endpoint is signup.
State lives in worker memory, which matches how the shared VPS instance
runs — one uvicorn worker (see scripts/keepalive.sh). A restart clears
the windows; for an anonymous-account-creation throttle that is fine and
keeps the backend free of redis/limits dependencies.
"""

import threading
import time
from collections import deque


class SlidingWindowLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str, limit: int, window_seconds: float) -> tuple[bool, float]:
        """Record an attempt for `key`; return (allowed, retry_after_seconds).

        Every arriving attempt counts, including ones that later fail for
        other reasons (duplicate email) — the alternative is letting an
        attacker burn the window with cheap rejects. limit <= 0 disables.
        """
        if limit <= 0:
            return True, 0.0
        now = time.monotonic()
        with self._lock:
            window = self._hits.setdefault(key, deque())
            while window and now - window[0] >= window_seconds:
                window.popleft()
            if len(window) >= limit:
                retry = window_seconds - (now - window[0])
                return False, max(1.0, retry)
            window.append(now)
            return True, 0.0

    def clear(self, key: str) -> None:
        """Forget a key's window (S44: a successful login resets its counter)."""
        with self._lock:
            self._hits.pop(key, None)

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


# Shared limiter for POST /api/auth/signup. Keyed by client IP.
signup_limiter = SlidingWindowLimiter()

# S49: shared limiter for POST /api/bridge/pair (the CLI pastes a pairing
# token here before dialing the WS hub). This endpoint has no user JWT — the
# token IS the consent proof — so anonymous token-guessing must be throttled.
# Callers only burn the window on FAILED redemptions (a successful pair clears
# the key), same shape as the login limiter above.
pair_limiter = SlidingWindowLimiter()

# S44: shared limiter for POST /api/auth/login. Keyed by client IP + lowercased
# email. Unlike signup, callers only burn the window on FAILED attempts (see
# auth.login), so a correct password never queues behind an attacker hammering
# the same pair; a success clears the key outright.
login_limiter = SlidingWindowLimiter()
