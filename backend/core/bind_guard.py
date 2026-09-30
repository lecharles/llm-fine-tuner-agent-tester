"""S15 (#17): refuse local_mode on a non-loopback bind.

local_mode (Phase 6 slice 3) is a single-user bootstrap: it auto-provisions
one local identity and skips JWT auth entirely. It is only safe while the
backend is reachable from the machine it runs on — the Mac CLI always binds
127.0.0.1. A shared/hosted instance (VPS team box on :8090, or anything
bindable from the internet) must never serve it.

Two enforcement points, one module:

1. `ensure_local_mode_bind_ok()` runs on app startup. uvicorn's --host is
   not passed to the ASGI app, but `python -m uvicorn` runs in-process, so
   the bind host is visible in sys.argv. LOCAL_MODE=true + --host 0.0.0.0
   (or any non-loopback address) raises and uvicorn exits before serving —
   the acceptance criterion from issue #17.

2. The HTTP middleware refuses every non-loopback TCP peer with 403 while
   local_mode is on. This is defense in depth for binds the argv sniff
   can't see (uvicorn --fd passing, config-file binds, proxy setups), and
   keeps /health answerable so monitors still get a liveness signal.
"""

import sys
from contextlib import suppress
from ipaddress import IPv6Address, ip_address

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from config import settings

# Starlette TestClient default peer name; treat it (and unix sockets) as
# local so the hermetic test suite keeps working without special hosts.
_LOCAL_HOSTNAMES = {"localhost", "testclient", "testserver"}


def is_loopback(host: str | None) -> bool:
    """True if `host` names a loopback address or is unknowable (local)."""
    if host is None or host == "" or host.lower() in _LOCAL_HOSTNAMES:
        return True
    try:
        ip = ip_address(host)
    except ValueError:
        return False
    if isinstance(ip, IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    return ip.is_loopback


def uvicorn_bind_host(argv: list[str] | None = None) -> str | None:
    """Pull --host out of the `python -m uvicorn` command line, if present."""
    args = sys.argv if argv is None else list(argv)
    host: str | None = None
    for i, arg in enumerate(args):
        if arg == "--host" and i + 1 < len(args):
            host = args[i + 1]
        elif arg.startswith("--host="):
            host = arg.split("=", 1)[1]
    return host


def ensure_local_mode_bind_ok(argv: list[str] | None = None) -> None:
    """Startup refusal: LOCAL_MODE=true on a non-loopback bind must not serve.

    No --host flag means uvicorn's default bind (127.0.0.1), which is safe.
    """
    if not settings.local_mode:
        return
    host = uvicorn_bind_host(argv)
    if host is not None and not is_loopback(host):
        raise RuntimeError(
            "Refusing to start: LOCAL_MODE=true requires a loopback bind, "
            f"but uvicorn was started with --host {host!r}. local_mode skips "
            "login for everyone who can reach the port. Unset LOCAL_MODE on "
            "shared/hosted instances (see docs/CREDENTIALS.md)."
        )


def register(app: FastAPI) -> None:
    """Wire the per-request peer guard onto the app.

    The startup refusal is called from the app lifespan (see main.py) —
    it has to run before the first request is served.
    """

    @app.middleware("http")
    async def local_mode_bind_guard(request: Request, call_next):
        if settings.local_mode and request.url.path != "/health":
            host = request.client.host if request.client else None
            if not is_loopback(host):
                return JSONResponse(
                    status_code=403,
                    content={
                        "detail": "local_mode refuses non-loopback peers; "
                        "unset LOCAL_MODE on shared/hosted instances "
                        "(see docs/CREDENTIALS.md)",
                    },
                )
        return await call_next(request)
