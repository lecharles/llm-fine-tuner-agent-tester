"""Serve the built frontend from the API process (Phase 6 slice 1).

One-port local experience: FastAPI owns :8000 and also serves the production
build of the React app. The dev flow is unchanged: if the frontend has not
been built (no dist/), the mount is skipped and Vite's dev proxy stays in play.
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from config import settings


def dist_dir() -> Path:
    if settings.static_dir:
        return Path(settings.static_dir)
    return Path(__file__).resolve().parent.parent / "frontend" / "dist"


def spa_is_built() -> bool:
    return (dist_dir() / "index.html").is_file()


def mount_spa(app: FastAPI) -> bool:
    """Mount the SPA so one process serves API and UI. Returns True when active."""
    root = dist_dir()
    if not spa_is_built():
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
