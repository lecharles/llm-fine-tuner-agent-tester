"""Phase 6 S7: macOS menu-bar extra for llmtuner (issue #7).

A tiny status item in the top-right menu bar showing whether the local
backend is answering /health:

    🟢 llmtuner   — server up
    🔴 llmtuner   — server down

Clicking the icon shows: Open window · Start server · Stop server · Quit.
"Quit" also stops a server that this menu-bar app started.

`rumps` is an OPTIONAL dependency (macOS only):

    pip install rumps

If it is missing, `llmtuner menubar` prints the install hint and exits 1 —
the rest of the CLI keeps working. This module must never import rumps at
module top level, so `python -m llmtuner --help` works everywhere.
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

RUNNING_TITLE = "🟢 llmtuner"
STOPPED_TITLE = "🔴 llmtuner"


def _import_rumps():
    """Import rumps lazily; return (module, error_message)."""
    try:
        import rumps  # noqa: PLC0415 (intentionally lazy/optional)

        return rumps, None
    except ImportError:
        hint = (
            "❌ 'rumps' is not installed — the menu-bar extra needs it "
            "(macOS only).\n"
            "   Install:  pip install rumps\n"
            "   Then run: python -m llmtuner menubar --port <port>"
        )
        return None, hint


def _repo_root() -> Path:
    # cli/llmtuner/menubar.py -> repo root is two levels above cli/
    return Path(__file__).resolve().parent.parent.parent


def _backend_python() -> str:
    repo = _repo_root()
    venv_python = repo / "backend" / ".venv-smoke" / "bin" / "python"
    if venv_python.exists():
        return str(venv_python)
    return shutil.which("python3") or sys.executable


def _health_ok(port: int, timeout: float = 1.0) -> bool:
    url = f"http://127.0.0.1:{port}/health"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return resp.status == 200
    except Exception:
        return False


class LLMTunerMenuBar:
    """Thin wrapper around a rumps.App; instantiated only inside run()."""

    def __init__(self, rumps, port: int):
        self.rumps = rumps
        self.port = port
        self.server_proc: subprocess.Popen | None = None
        self._stopping = False

        app = rumps.App("llmtuner", title=STOPPED_TITLE, quit_button=None)
        self.open_item = rumps.MenuItem("Open window", callback=self._open_window)
        self.start_item = rumps.MenuItem("Start server", callback=self._start_server)
        self.stop_item = rumps.MenuItem("Stop server", callback=self._stop_server)
        self.quit_item = rumps.MenuItem("Quit", callback=self._quit)
        app.menu = [
            self.open_item,
            None,
            self.start_item,
            self.stop_item,
            None,
            self.quit_item,
        ]
        self.app = app

    # -- status polling -------------------------------------------------

    def _refresh(self, _timer=None):
        running = _health_ok(self.port)
        self.app.title = RUNNING_TITLE if running else STOPPED_TITLE
        self.start_item.set_enable(not running)
        self.stop_item.set_enable(running)

    # -- menu callbacks --------------------------------------------------

    def _open_window(self, _sender=None):
        repo = _repo_root()
        env = os.environ.copy()
        env["PYTHONPATH"] = str(repo / "cli") + os.pathsep + env.get("PYTHONPATH", "")
        subprocess.Popen(
            [_backend_python(), "-m", "llmtuner", "app", "--port", str(self.port), "--fresh"],
            cwd=repo,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def _spawn_server(self):
        repo = _repo_root()
        backend_dir = repo / "backend"
        env = os.environ.copy()
        env["LOCAL_MODE"] = "true"
        self.server_proc = subprocess.Popen(
            [_backend_python(), "-m", "uvicorn", "main:app",
             "--host", "127.0.0.1", "--port", str(self.port)],
            cwd=backend_dir,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def _start_server(self, _sender=None):
        if _health_ok(self.port):
            self.rumps.notification("llmtuner", "Server already running",
                                    f"http://127.0.0.1:{self.port} answers /health")
            return
        if self.server_proc is not None and self.server_proc.poll() is None:
            self.rumps.notification("llmtuner", "Server is booting",
                                    "uvicorn was started from the menu bar and is not up yet.")
            return
        self._spawn_server()
        self.rumps.notification("llmtuner", "Starting server",
                                f"uvicorn launching on :{self.port} (first boot can take ~30s).")

    def _kill_child(self):
        """Terminate a server we started. Returns True if we killed one."""
        proc = self.server_proc
        if proc is not None and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
            self.server_proc = None
            return True
        self.server_proc = None
        return False

    def _stop_server(self, _sender=None):
        if self._kill_child():
            self.rumps.notification("llmtuner", "Server stopped", "Started by the menu bar.")
            return
        if _health_ok(self.port):
            self.rumps.notification(
                "llmtuner", "Can't stop this server",
                f":{self.port} was started outside the menu bar — stop it in its Terminal.",
            )
        else:
            self.rumps.notification("llmtuner", "Server already stopped",
                                    f"Nothing answering on :{self.port}.")

    def _quit(self, _sender=None):
        self._kill_child()
        self.rumps.stop_app()

    def run(self) -> int:
        timer = self.rumps.Timer(self._refresh, 3)
        timer.start()
        self._refresh()
        self.app.run()
        return 0


def menubar(port: int = 8000) -> int:
    """Entry point for `llmtuner menubar`."""
    rumps, hint = _import_rumps()
    if rumps is None:
        print(hint)
        if platform.system() != "Darwin":
            print("   Note: rumps only installs on macOS; this command is macOS-only.")
        return 1
    return LLMTunerMenuBar(rumps, port=port).run()
