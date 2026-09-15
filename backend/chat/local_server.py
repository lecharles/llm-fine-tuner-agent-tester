"""On-demand mlx_lm.server management for the local compare columns.

The compare view's two local columns expect mlx_lm.server to be listening on
the ports baked into chat/compare.py: the user's fused model on 8081 and its
untuned base on 8082. Nothing in the app ever started those processes, so
local columns silently connection-refused. This module starts them the first
time a chat turn needs them, waits for readiness, restarts them if the pinned
model changes, and shuts them down when the API process exits.
"""

import atexit
import os
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

from chat.compare import FINE_TUNED_BASE_URL, VANILLA_BASE_URL
from config import llmtuner_home

# mlx_lm.server startup loads the weights: a 2+GB fused bf16 model can take a
# minute or two on a busy machine. Generous, but bounded: the chat turn surfaces
# a clear error after this instead of hanging forever.
STARTUP_TIMEOUT_SECONDS = 240
PORTS = {
    "fine_tuned": urlparse(FINE_TUNED_BASE_URL).port,
    "vanilla": urlparse(VANILLA_BASE_URL).port,
}

_lock = threading.Lock()
# label -> (model_identity, Popen). Tracked so a model change restarts cleanly
# and the API shutdown can reap its children.
_servers: dict[str, tuple[str, subprocess.Popen]] = {}
_shutdown_registered = False


def _log_path(label: str, port: int) -> Path:
    d = llmtuner_home() / "servers"
    d.mkdir(parents=True, exist_ok=True)
    return d / f"mlx_server_{label}_{port}.log"


def _server_command(model: str, port: int) -> list[str]:
    """Prefer the venv's mlx_lm.server script; fall back to invoking its main()
    through the interpreter so a PATH gap can never block the fallback."""
    exe = Path(sys.executable).with_name("mlx_lm.server")
    base_args = ["--model", model, "--port", str(port), "--host", "127.0.0.1"]
    if exe.exists():
        return [str(exe), *base_args]
    return [sys.executable, "-c", "from mlx_lm.server import main; main()", *base_args]


def _port_responding(port: int) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/v1/models", timeout=1):
            return True
    except urllib.error.HTTPError:
        return True  # something is answering HTTP; good enough to probe
    except Exception:
        return False


def _reap():
    """Terminate every server child we started. Registered with atexit."""
    with _lock:
        for label, (_model, proc) in list(_servers.items()):
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
        _servers.clear()


def _ensure_one(label: str, model: str, results: dict) -> None:
    port = PORTS[label]
    with _lock:
        proc = _servers.get(label)
        if proc and proc[0] != model:
            # The pinned fine-tuned model changed: restart with the new weights.
            proc[1].terminate()
            _servers.pop(label, None)
            proc = None
            for _ in range(20):
                if not _port_responding(port):
                    break
                time.sleep(0.5)
        elif proc and proc[1].poll() is not None:
            # We started it earlier but it died since; respawn below.
            _servers.pop(label, None)
            proc = None
        if proc:
            # Alive and serving the right model; fall through to the wait loop.
            proc = proc[1]
        elif _port_responding(port):
            # Somebody already serves this port (e.g. a manual mlx_lm.server);
            # trust it rather than fighting over the socket.
            results[label] = None
            return
        else:
            log_file = open(_log_path(label, port), "w", encoding="utf-8")
            try:
                proc = subprocess.Popen(
                    _server_command(model, port),
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                    env=os.environ.copy(),
                )
            except FileNotFoundError as exc:
                results[label] = f"could not start mlx_lm.server: {exc}"
                return
            finally:
                log_file.close()
            _servers[label] = (model, proc)

    deadline = time.time() + STARTUP_TIMEOUT_SECONDS
    while time.time() < deadline:
        if _port_responding(port):
            results[label] = None
            return
        if proc.poll() is not None:
            tail = _log_path(label, port).read_text(errors="replace")[-400:]
            results[label] = (
                f"mlx_lm.server for {label} exited (code {proc.returncode}); "
                f"last log lines:\n{tail}"
            )
            return
        time.sleep(1)
    results[label] = (
        f"mlx_lm.server for {label} not ready after {STARTUP_TIMEOUT_SECONDS}s "
        f"(model still loading? log: {_log_path(label, port)})"
    )


def ensure_local_servers(fine_tuned_model: str, base_model: str) -> dict[str, str | None]:
    """Make both local compare endpoints answer. Returns {label: error|None};
    callers treat an error string as 'this column cannot reply this turn'."""
    global _shutdown_registered
    with _lock:
        if not _shutdown_registered:
            atexit.register(_reap)
            _shutdown_registered = True
    wanted = {"fine_tuned": fine_tuned_model, "vanilla": base_model}
    results: dict[str, str | None] = {}
    threads = [
        threading.Thread(target=_ensure_one, args=(label, model, results), daemon=True)
        for label, model in wanted.items()
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=STARTUP_TIMEOUT_SECONDS + 10)
    return results
