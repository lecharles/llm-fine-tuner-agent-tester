"""Serve the built frontend from the API process (Phase 6 slice 1).

One-port local experience: FastAPI owns :8000 and also serves the production
build of the React app. The dev flow is unchanged: if the frontend has not
been built (no dist/), the mount is skipped and Vite's dev proxy stays in play.
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from config import settings


def dist_dir() -> Path:
    if settings.static_dir:
        return Path(settings.static_dir)
    return Path(__file__).resolve().parent.parent / "frontend" / "dist"


def spa_is_built() -> bool:
    return (dist_dir() / "index.html").is_file()


SPLASH_HTML = """<!doctype html>
<html><head><meta charset="utf-8"><title>LLM Tuner — server up</title>
<style>
 body{background:#0b0b10;color:#e8e8f0;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;
      display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0}
 .card{max-width:640px;padding:40px;border:1px solid #2a2a38;border-radius:14px;background:#12121a}
 h1{font-size:20px;margin:0 0 6px} .dot{color:#7c6cf0}
 p{color:#9a9ab0;font-size:13px;line-height:1.6}
 table{width:100%;border-collapse:collapse;margin:18px 0;font-size:13px}
 td{padding:6px 8px;border-bottom:1px solid #1e1e28}
 td:last-child{text-align:right}
 .ok{color:#4ade80} .bad{color:#f87171}
 code{background:#1c1c26;padding:2px 6px;border-radius:4px}
</style></head><body><div class="card">
<h1><span class="dot">●</span> LLM Tuner server is up</h1>
<p>The API process is alive and reachable. The React UI build was not found,
so this status page is being served instead.</p>
<table>
<tr><td>API / health</td><td class="ok">ok</td></tr>
<tr><td>Local mode</td><td>@@local_mode@@</td></tr>
<tr><td>Database</td><td><code>@@db_path@@</code></td></tr>
<tr><td>Anthropic key (generation)</td><td>@@anthropic@@</td></tr>
<tr><td>OpenAI key (compare)</td><td>@@openai@@</td></tr>
<tr><td>UI build expected at</td><td><code>@@dist@@</code></td></tr>
</table>
<p>Build the UI: <code>cd frontend && npm ci && npm run build</code>, then reload.<br>
Add or fix API keys in <code>~/.llmtuner/.env</code> and restart with <code>llmtuner up</code>.</p>
</div></body></html>"""


def render_splash() -> str:
    from config import settings

    def badge(value) -> str:
        return '<span class="ok">set</span>' if value else '<span class="bad">not set</span>'

    # Token replacement, not str.format: the CSS block is full of literal { }.
    html = SPLASH_HTML
    for token, value in {
        "@@local_mode@@": '<span class="ok">on</span>' if settings.local_mode else '<span class="bad">off</span>',
        "@@db_path@@": settings.resolved_database_url().replace("sqlite:///", ""),
        "@@anthropic@@": badge(settings.anthropic_api_key),
        "@@openai@@": badge(settings.openai_api_key),
        "@@dist@@": str(dist_dir()),
    }.items():
        html = html.replace(token, value)
    return html


def mount_spa(app: FastAPI) -> bool:
    """Mount the SPA so one process serves API and UI. Returns True when active."""
    root = dist_dir()
    if not spa_is_built():
        # Phase 6 slice 6: even without a UI build, the browser should land on a
        # real page the moment the server is reachable — a static status splash.
        @app.get("/", include_in_schema=False)
        def splash():
            return HTMLResponse(render_splash())

        return False

    app.mount("/assets", StaticFiles(directory=root / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa_fallback(full_path: str):
        # Unknown /api/* paths must stay JSON 404s, not HTML.
        if full_path.startswith("api/"):
            return JSONResponse({"detail": "Not Found"}, status_code=404)
        candidate = (root / full_path).resolve()
        if (
            full_path
            and candidate.is_file()
            and candidate.is_relative_to(root.resolve())
        ):
            return FileResponse(candidate)
        # Deep links like /train or /datasets/4 are client-side routes.
        return FileResponse(root / "index.html")

    return True
