"""S44: CSP + baseline security headers for the served web shell.

Pure-ASGI middleware (not BaseHTTPMiddleware): it only edits the http
response start message, so WebSocket upgrade responses (the S25/S26
bridge at /companion/ws) and streaming responses pass through untouched.

Headers applied to every http response:
- X-Content-Type-Options: nosniff
- Referrer-Policy: no-referrer  (the app never needs a cross-origin referrer;
  all provider API calls happen server-side)
- X-Frame-Options: DENY         (belt for frame-ancestors below)
- Content-Security-Policy: same-origin everything, with two deliberate
  concessions: `style-src 'unsafe-inline'` because React writes inline style
  attributes and the no-build splash page uses an inline <style> block; and
  no external script sources — the Vite build ships exactly one same-origin
  module script (verified against frontend/dist/index.html at S44 time).

/docs and /redoc are exempt from the CSP *only*: FastAPI's Swagger UI pulls
its JS/CSS from the swagger CDN, so shipping the CSP there would just break
the dev docs page. Everything else (incl. the API and the SPA) is covered.

Local dev via Vite's own server (:5173) is unaffected — this middleware
lives in the API process, which is the thing that ships the shell on :8090.
"""

# No external hosts allowed; 'unsafe-inline' limited to styles (see module doc).
CSP_HEADER = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data:; "
    "font-src 'self' data:; "
    "connect-src 'self'; "
    "object-src 'none'; "
    "frame-ancestors 'none'; "
    "base-uri 'self'; "
    "form-action 'self'"
)

BASE_HEADERS = [
    (b"x-content-type-options", b"nosniff"),
    (b"referrer-policy", b"no-referrer"),
    (b"x-frame-options", b"DENY"),
]

# Swagger/ReDoc pull CDN assets; exempt the CSP on those two paths only.
CSP_EXEMPT_PATHS = {"/docs", "/redoc"}


class SecurityHeadersMiddleware:
    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        headers = list(BASE_HEADERS)
        if path not in CSP_EXEMPT_PATHS:
            headers.append((b"content-security-policy", CSP_HEADER.encode("ascii")))

        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                existing = message.get("headers") or []
                # We own these header names; drop any prior value, then append ours.
                names = {n.lower() for n, _ in headers}
                kept = [(n, v) for n, v in existing if n.lower() not in names]
                message = {**message, "headers": kept + headers}
            await send(message)

        await self.app(scope, receive, send_with_headers)


def register(app) -> None:
    """Add the middleware. Call AFTER CORS-style middlewares if any are ever
    added, so preflight short-circuits still carry the headers."""
    app.add_middleware(SecurityHeadersMiddleware)
