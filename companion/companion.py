"""llmtuner companion — S24 (issue #27): local-device runtime skeleton.

The companion runs on the user's Mac, takes requests from the web shell over a
WebSocket **dial-out** connection, and drives train / fuse / export / serve
against the local MLX pipeline + Ollama. The transport choice follows
docs/ADR-001.md ("decide before S24"): dial-out avoids NAT traversal and the
mixed-content problem an https web shell would hit against a loopback endpoint,
and the pairing token rides inside the hello frame (never in a URL, which
shows up in logs).

STATUS: skeleton, by design. The hub endpoint that accepts these sessions
lands in S25 (#28); the hosted job queue and artifact pinning land with the
S26 data split (#29). Until then the only honest ways to exercise this file
are `--self-test` (in-process fake hub + fake API; runs anywhere with
`pip install -r companion/requirements.txt`) and the Mac recipes in the S24
commit body.

Usage:
    python companion/companion.py --hub wss://HOST/companion/ws \\
        --name studio-mac              # token via LLMTUNER_PAIRING_TOKEN
    python companion/companion.py --self-test

Protocol (JSON frames, protocol id "llmtuner-companion/0"):
    c->h  {"type":"hello","protocol":...,"name":...,"token":...,"capabilities":{...}}
    h->c  {"type":"welcome","companion_id":...}  |  {"type":"error","detail":...}
    h->c  {"type":"job","id":...,"kind":"status|train|fuse|export|serve","payload":{...}}
    c->h  {"type":"event","id":...,"stage":...,"detail":...}     (progress, many)
    c->h  {"type":"result","id":...,"ok":bool,"data":{...}}      (exactly one per job)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import platform
import shutil
import subprocess
import sys
import threading
import urllib.error
import urllib.request
from pathlib import Path

PROTOCOL = "llmtuner-companion/0"
REPO = Path(__file__).resolve().parent.parent
BACKEND_DIR = REPO / "backend"
API_DEFAULT = "http://127.0.0.1:8321"
OLLAMA_DEFAULT = "http://127.0.0.1:11434"
TERMINAL_STATUSES = {"completed", "failed"}
POLL_DEFAULT = 5.0
TRAIN_DEADLINE_S = 2 * 60 * 60  # two hours is plenty for a 1B LoRA run
LOSS_CHUNK_POINTS = 80  # S50: loss frames are bounded so the 1 MiB ws cap is never at risk


def log(msg: str) -> None:
    """Console log. Never call this with the pairing token in it."""
    print(f"[companion] {msg}", flush=True)


class HubAuthError(RuntimeError):
    """The hub rejected our hello (bad pairing token, unknown companion...).
    Retrying cannot fix this, so the reconnect loop stops on it."""


def backend_python() -> str:
    """Python that has the backend + MLX deps, installer layout first.

    ~/.llmtuner (install/macos.sh) puts the venv at REPO/.venv; the dev VPS
    checkout keeps backend/.venv-smoke. Fall back to whatever is running us.
    """
    for candidate in (REPO / ".venv" / "bin" / "python",
                      BACKEND_DIR / ".venv-smoke" / "bin" / "python"):
        if candidate.exists():
            return str(candidate)
    return sys.executable


def probe_capabilities() -> dict:
    """Cheap, non-interactive device snapshot sent in hello and status jobs."""
    mlx_ok = False
    try:
        import mlx_lm  # noqa: F401
        mlx_ok = True
    except Exception:
        pass
    ollama_ok = bool(shutil.which("ollama"))
    try:
        free_gb = round(shutil.disk_usage(Path.home()).free / (102 ** 3), 1)
    except OSError:
        free_gb = None
    return {
        "platform": platform.system().lower(),
        "machine": platform.machine(),
        "python": platform.python_version(),
        "mlx_lm": mlx_ok,
        "ollama": ollama_ok,
        "disk_free_gb": free_gb,
    }


def http_json(method: str, url: str, body: dict | None = None, timeout: float = 15.0):
    """Small sync JSON HTTP helper; returns (status_code, parsed_body_or_text)."""
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url, data=data, method=method,
        headers={"Content-Type": "application/json"} if data else {},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode(errors="replace")
            return resp.status, _maybe_json(raw)
    except urllib.error.HTTPError as err:
        raw = err.read().decode(errors="replace")
        return err.code, _maybe_json(raw)
    except (urllib.error.URLError, TimeoutError, OSError) as err:
        return 0, f"unreachable: {err}"


def _maybe_json(raw: str):
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw[:500]


# The backend-side helper a fuse/export job runs (cwd=backend so it can import
# the app's own modules — path layout stays single-sourced in training.runner).
FUSE_SCRIPT = """
import json, sys, traceback
run_id = int(sys.argv[1])
try:
    from database import SessionLocal
    from models.training_run import TrainingRun
    from training.runner import run_dir_for
    from training.export import export_gguf
    db = SessionLocal()
    run = db.query(TrainingRun).filter(TrainingRun.id == run_id).first()
    if run is None:
        raise RuntimeError(f"no training run {run_id} on this device")
    workspace = run_dir_for(run_id)
    adapter_dir = workspace / "adapters"
    if not adapter_dir.exists():
        raise RuntimeError(f"no adapter dir at {adapter_dir} — train the run first")
    out = export_gguf(run.base_model, adapter_dir, workspace / "fused_model")
    print("RESULT" + json.dumps(out))
except Exception:
    print("ERROR" + traceback.format_exc())
    sys.exit(1)
"""


class Companion:
    def __init__(self, hub: str, token: str, name: str, api: str = API_DEFAULT,
                 ollama_base: str = OLLAMA_DEFAULT, *, start_backend: bool = True,
                 poll_interval: float = POLL_DEFAULT, deadline_s: float = TRAIN_DEADLINE_S):
        self.hub = hub
        self.token = token
        self.name = name
        self.api = api.rstrip("/")
        self.ollama_base = ollama_base.rstrip("/")
        self.start_backend = start_backend
        self.poll_interval = poll_interval
        self.deadline_s = deadline_s
        self.backend_proc: subprocess.Popen | None = None
        self._send_lock = asyncio.Lock()
        self._tasks: set[asyncio.Task] = set()
        self._stop = asyncio.Event()

    # ---------- transport ----------

    async def _send(self, ws, obj: dict) -> None:
        async with self._send_lock:
            await ws.send(json.dumps(obj))

    async def run(self) -> int:
        """Dial out, serve jobs, reconnect with capped backoff. 0 = hub closed
        the session politely; 2 = hub rejected us (never retry-loop that)."""
        import websockets  # noqa: F401 — installed via companion/requirements.txt

        attempt = 0
        while not self._stop.is_set():
            try:
                return await self._session()
            except HubAuthError as err:
                log(f"hub rejected the pairing: {err}")
                return 2
            except asyncio.CancelledError:
                raise
            except Exception as err:  # connection dropped, hub restarting, ...
                delay = min(60.0, 2.0 ** attempt)
                attempt += 1
                log(f"hub session ended ({type(err).__name__}: {err}); "
                    f"redialing in {delay:.0f}s")
                self._cleanup_backend()
                try:
                    await asyncio.wait_for(self._stop.wait(), timeout=delay)
                    return 0
                except asyncio.TimeoutError:
                    continue
        return 0

    async def _session(self) -> int:
        import websockets

        log(f"dialing out to {self.hub}")
        async with websockets.connect(self.hub, ping_interval=20, ping_timeout=20,
                                      max_size=2 ** 20) as ws:
            caps = await asyncio.to_thread(probe_capabilities)
            await self._send(ws, {
                "type": "hello", "protocol": PROTOCOL,
                "name": self.name, "token": self.token, "capabilities": caps,
            })
            first = _maybe_json(await ws.recv())
            if not isinstance(first, dict):
                raise ValueError("hub sent a non-JSON welcome frame")
            if first.get("type") == "error":
                raise HubAuthError(str(first.get("detail", "rejected"))[:300])
            if first.get("type") != "welcome":
                raise HubAuthError(f"expected welcome, got {first.get('type')!r}")
            log(f"paired as companion {first.get('companion_id', '?')} on "
                f"{caps['platform']}/{caps['machine']} mlx={caps['mlx_lm']} "
                f"ollama={caps['ollama']}")
            async for raw in ws:
                msg = _maybe_json(raw)
                if isinstance(msg, dict) and msg.get("type") == "job":
                    task = asyncio.create_task(self._handle_job(ws, msg))
                    self._tasks.add(task)
                    task.add_done_callback(self._tasks.discard)
        return 0

    async def close(self) -> None:
        self._stop.set()
        self._cleanup_backend()

    def _cleanup_backend(self) -> None:
        if self.backend_proc and self.backend_proc.poll() is None:
            self.backend_proc.terminate()
        self.backend_proc = None

    # ---------- local backend ----------

    async def backend_up(self) -> bool:
        code, _ = await asyncio.to_thread(http_json, "GET", f"{self.api}/health", None, 2.0)
        return code == 200

    async def ensure_local_backend(self) -> bool:
        if await self.backend_up():
            return True
        if not self.start_backend:
            return False
        port = self.api.rsplit(":", 1)[-1].split("/")[0]
        env = os.environ.copy()
        env["LOCAL_MODE"] = "true"  # loopback single-user bootstrap (S15 refuses other binds)
        log(f"starting local backend on {self.api}")
        try:
            self.backend_proc = subprocess.Popen(
                [backend_python(), "-m", "uvicorn", "main:app",
                 "--host", "127.0.0.1", "--port", port],
                cwd=BACKEND_DIR, env=env,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        except OSError as err:
            log(f"could not start backend: {err}")
            return False
        for _ in range(120):
            if await self.backend_up():
                return True
            await asyncio.sleep(0.5)
        return False

    # ---------- job dispatch ----------

    async def _result(self, ws, job_id: str, ok: bool, data: dict) -> None:
        await self._send(ws, {"type": "result", "id": job_id, "ok": ok, "data": data})

    async def _event(self, ws, job_id: str, stage: str, detail: str = "",
                     data: dict | None = None) -> None:
        frame: dict = {"type": "event", "id": job_id, "stage": stage, "detail": detail[:500]}
        if data:
            frame["data"] = data
        await self._send(ws, frame)

    async def _handle_job(self, ws, msg: dict) -> None:
        job_id, kind = str(msg.get("id", "?")), str(msg.get("kind", ""))
        payload = msg.get("payload") or {}
        handlers = {"status": self.job_status, "train": self.job_train,
                    "fuse": self.job_fuse, "export": self.job_fuse,  # export == fuse step today
                    "serve": self.job_serve}
        handler = handlers.get(kind)
        if handler is None:
            await self._result(ws, job_id, False, {"detail": f"unknown job kind {kind!r}"})
            return
        try:
            await handler(ws, job_id, payload)
        except Exception as err:  # a crashing job must not kill the session
            await self._result(ws, job_id, False,
                               {"detail": f"{type(err).__name__}: {err}"})

    async def job_status(self, ws, job_id: str, payload: dict) -> None:
        caps = await asyncio.to_thread(probe_capabilities)
        up = await self.backend_up()
        await self._result(ws, job_id, True,
                           {"capabilities": caps, "api": self.api, "backend_up": up})

    async def job_train(self, ws, job_id: str, payload: dict) -> None:
        """S50: the train handoff. Two input shapes:
          - legacy: payload.dataset_id (int) — the local DB already has the dataset.
          - bridge handoff: payload.hosted_dataset = {name, pairs:[{question,answer}]}
            — the companion materializes it in the local DB first, then trains.
        Hyperparameters ride through unchanged. Loss points stream back to the
        hub in bounded chunks via `event` frames with `data.points`."""
        # Materialize a hosted dataset if the hub shipped one.
        hosted = payload.get("hosted_dataset")
        dataset_id = payload.get("dataset_id")
        if isinstance(hosted, dict) and hosted.get("pairs"):
            await self._event(ws, job_id, "materializing",
                              f"{len(hosted['pairs'])} QA pairs from the hub")
            local_id, detail = await asyncio.to_thread(
                self._local_dataset_from_hosted, hosted)
            if local_id is None:
                await self._result(ws, job_id, False, {"detail": detail})
                return
            dataset_id = local_id
        if not isinstance(dataset_id, int) or dataset_id < 1:
            await self._result(ws, job_id, False, {
                "detail": "payload.dataset_id (int) or hosted_dataset (web train handoff) required"})
            return
        iters = payload.get("iters", 300)
        try:
            iters = max(1, min(5000, int(iters)))
        except (TypeError, ValueError):
            iters = 300
        if not await self.ensure_local_backend():
            await self._result(ws, job_id, False,
                               {"detail": f"local backend not reachable at {self.api} "
                                          "and auto-start failed (try `llmtuner up`)"})
            return

        # Build the run body. The local API accepts the S33 hyperparameter
        # fields; forward them only when the hub payload carried them, so the
        # legacy direct-call path still works unchanged.
        run_body: dict = {"dataset_id": dataset_id, "iters": iters}
        for key in ("lora_rank", "lora_alpha"):
            v = payload.get(key)
            if isinstance(v, int) and v >= 1:
                run_body[key] = v
        lr = payload.get("learning_rate")
        if isinstance(lr, (int, float)) and 0 < float(lr) <= 1:
            run_body["learning_rate"] = float(lr)
        base = payload.get("base_model")
        if isinstance(base, str) and base.strip():
            run_body["base_model"] = base.strip()

        await self._event(ws, job_id, "submitting",
                          f"dataset {dataset_id}, {iters} iters")
        code, created = await asyncio.to_thread(
            http_json, "POST", f"{self.api}/api/training-runs", run_body)
        if code != 201 or not isinstance(created, dict):
            detail = created.get("detail", str(created)) if isinstance(created, dict) else str(created)
            await self._result(ws, job_id, False,
                               {"status_code": code, "detail": str(detail)[:500]})
            return
        run_id = created["id"]
        loop = asyncio.get_running_loop()
        deadline = loop.time() + self.deadline_s
        status = created.get("status", "queued")
        run: dict = created
        sent_losses = 0
        while status not in TERMINAL_STATUSES:
            if loop.time() > deadline:
                await self._result(ws, job_id, False,
                                  {"run_id": run_id, "detail": f"no terminal status after {int(self.deadline_s)}s"})
                return
            await asyncio.sleep(self.poll_interval)
            code, latest = await asyncio.to_thread(
                http_json, "GET", f"{self.api}/api/training-runs/{run_id}", None, 10.0)
            if code != 200 or not isinstance(latest, dict):
                await self._event(ws, job_id, "poll-error", f"HTTP {code}")
                continue
            run = latest
            status = run.get("status", status)
            _, losses = await asyncio.to_thread(
                http_json, "GET", f"{self.api}/api/training-runs/{run_id}/losses", None, 10.0)
            if isinstance(losses, list) and len(losses) > sent_losses:
                # Stream only the NEW points since the last poll, in chunks
                # small enough to fit comfortably under the companion's 1 MiB
                # inbound cap even on a giant burst.
                new_points = losses[sent_losses:]
                for i in range(0, len(new_points), LOSS_CHUNK_POINTS):
                    chunk = new_points[i:i + LOSS_CHUNK_POINTS]
                    await self._event(ws, job_id, "loss",
                                      f"{len(chunk)} new points",
                                      {"points": chunk})
                sent_losses = len(losses)
            await self._event(ws, job_id, status,
                              f"run {run_id} · {len(losses) if isinstance(losses, list) else 0} loss points")
        if status == "completed":
            await self._result(ws, job_id, True,
                               {"run_id": run_id, "status": status,
                                "base_model": run.get("base_model"),
                                "iters": run.get("iters")})
        else:
            await self._result(ws, job_id, False,
                               {"run_id": run_id, "status": status,
                                "detail": str(run.get("error_message") or "failed")[:500]})

    def _local_dataset_from_hosted(self, hosted: dict) -> tuple[int | None, str]:
        """S50: write the hub's dataset into the local DB so the local
        trainer can see it. Sync helper (runs in a thread). Returns
        (dataset_id, detail) — detail is empty on success."""
        name = str(hosted.get("name") or "bridge dataset")[:100]
        pairs = hosted.get("pairs") or []
        code, created = http_json(
            "POST", f"{self.api}/api/datasets",
            {"name": name, "source": "bridge"})
        if code != 201 or not isinstance(created, dict) or "id" not in created:
            detail = created.get("detail", str(created)) if isinstance(created, dict) else str(created)
            return None, f"local dataset create failed (HTTP {code}): {detail}"[:500]
        dataset_id = created["id"]
        for i, pair in enumerate(pairs):
            q = str(pair.get("question", ""))[:4000]
            a = str(pair.get("answer", ""))[:4000]
            code, out = http_json(
                "POST", f"{self.api}/api/datasets/{dataset_id}/qa-pairs",
                {"question": q, "answer": a})
            if code != 201:
                detail = out.get("detail", str(out)) if isinstance(out, dict) else str(out)
                return None, f"pair {i + 1}/{len(pairs)} rejected (HTTP {code}): {detail}"[:500]
        return dataset_id, ""

    async def job_fuse(self, ws, job_id: str, payload: dict) -> None:
        run_id = payload.get("run_id")
        if not isinstance(run_id, int) or run_id < 1:
            await self._result(ws, job_id, False, {"detail": "payload.run_id (int) required"})
            return
        if not await self.ensure_local_backend():
            await self._result(ws, job_id, False, {"detail": "local backend unreachable"})
            return
        caps = await asyncio.to_thread(probe_capabilities)
        if not caps["mlx_lm"]:
            await self._result(ws, job_id, False,
                               {"detail": "mlx-lm not importable by the backend python — "
                                          "run inside the installer venv (source ~/.llmtuner/.venv/bin/activate)"})
            return
        await self._event(ws, job_id, "fusing", f"run {run_id}")
        proc = await asyncio.to_thread(
            subprocess.run,
            [backend_python(), "-c", FUSE_SCRIPT, str(run_id)],
            cwd=BACKEND_DIR, capture_output=True, text=True, timeout=60 * 60)
        out = proc.stdout
        if proc.returncode == 0 and "RESULT" in out:
            data = json.loads(out.split("RESULT", 1)[1].strip().splitlines()[0])
            await self._result(ws, job_id, True, {"run_id": run_id, **data})
        else:
            tail = (out.split("ERROR", 1)[-1] if "ERROR" in out else proc.stderr) or "no output"
            await self._result(ws, job_id, False,
                               {"run_id": run_id, "detail": tail[-500:],
                                "note": "real GGUF conversion is pending (Phase 4 line); "
                                        "this yields the fused bf16 model dir"})

    async def job_serve(self, ws, job_id: str, payload: dict) -> None:
        if "run_id" in payload and "model" not in payload:
            await self._result(ws, job_id, False,
                               {"detail": "serving a fine-tuned artifact on-device lands with "
                                          "the S26 data split (#29); serve jobs take {model} now"})
            return
        model = payload.get("model")
        if not isinstance(model, str) or not model.strip():
            await self._result(ws, job_id, False, {"detail": "payload.model (str, e.g. llama3.2:1b) required"})
            return
        model = model.strip()
        if not shutil.which("ollama"):
            await self._result(ws, job_id, False, {"detail": "ollama not installed (brew install ollama)"})
            return

        def pull_and_verify():
            proc = subprocess.Popen(["ollama", "pull", model],
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    text=True)
            lines = []
            assert proc.stdout is not None
            for line in proc.stdout:
                lines.append(line)
                if len(lines) % 40 == 0:
                    progress_events.append(lines[-1].strip()[:120])
            proc.wait()
            code, tags = http_json("GET", f"{self.ollama_base}/api/tags", None, 5.0)
            names = [m.get("name", "") for m in tags.get("models", [])] if code == 200 and isinstance(tags, dict) else []
            return proc.returncode, names, len(lines)

        progress_events: list[str] = []
        await self._event(ws, job_id, "pulling", model)
        rc, names, n_lines = await asyncio.to_thread(pull_and_verify)
        for stage_detail in progress_events:
            await self._event(ws, job_id, "pull-progress", stage_detail)
        present = any(n == model or n.startswith(model.split(":")[0] + ":") for n in names)
        await self._result(ws, job_id, rc == 0 and present,
                           {"model": model, "ollama_rc": rc, "installed": present,
                            "pull_lines": n_lines})


# ---------- self-test (fake hub + fake API, in one process, exits) ----------

async def self_test() -> int:
    import websockets
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    state = {"runs_seen": 0, "get_count": 0,
             "datasets_created": 0, "pairs_seen": 0,
             "run_bodies": []}

    class FakeAPI(BaseHTTPRequestHandler):
        def _send(self, code: int, obj) -> None:
            body = json.dumps(obj).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path == "/health":
                self._send(200, {"status": "ok"})
            elif self.path.startswith("/api/training-runs/") and self.path.endswith("/losses"):
                self._send(200, [{"step": 1, "loss": 2.0}, {"step": 2, "loss": 1.5}])
            elif self.path.startswith("/api/training-runs/"):
                state["get_count"] += 1
                status = "running" if state["get_count"] <= 1 else "completed"
                self._send(200, {"id": 7, "status": status, "base_model": "fake/base",
                                 "iters": 20, "error_message": None})
            else:
                self._send(404, {"detail": "no"})

        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length) or b"{}")
            if self.path == "/api/datasets":
                state["datasets_created"] += 1
                self._send(201, {"id": 42, "name": body.get("name"), "source": body.get("source")})
            elif self.path.startswith("/api/datasets/") and self.path.endswith("/qa-pairs"):
                state["pairs_seen"] += 1
                self._send(201, {"id": state["pairs_seen"], "question": body.get("question"),
                                 "answer": body.get("answer")})
            elif self.path == "/api/training-runs":
                state["runs_seen"] += 1
                state["run_bodies"].append(body)
                self._send(201, {"id": 7, "status": "queued", "base_model": "fake/base",
                                 "iters": body.get("iters", 20), "error_message": None})
            else:
                self._send(404, {"detail": "no"})

        def log_message(self, *args):  # quiet
            pass

    api = ThreadingHTTPServer(("127.0.0.1", 0), FakeAPI)
    api_port = api.server_address[1]
    threading.Thread(target=api.serve_forever, daemon=True).start()

    hub_out = {"welcome": False, "results": {}, "events": []}

    async def hub_handler(ws, path=None):  # path arg for older websockets APIs
        hello = json.loads(await ws.recv())
        assert hello["type"] == "hello" and hello["protocol"] == PROTOCOL
        if hello["token"] != "test-pair":
            await ws.send(json.dumps({"type": "error", "detail": "pairing token rejected"}))
            return
        assert hello["capabilities"]["platform"]
        await ws.send(json.dumps({"type": "welcome", "companion_id": "test-c1"}))
        jobs = [
            {"type": "job", "id": "j1", "kind": "status", "payload": {}},
            {"type": "job", "id": "j2", "kind": "train", "payload": {"dataset_id": 3, "iters": 20}},
            {"type": "job", "id": "j3", "kind": "bogus", "payload": {}},
            # S50: the bridge handoff — hosted_dataset materialization + hyperparameters.
            {"type": "job", "id": "j4", "kind": "train",
             "payload": {"hosted_dataset": {"name": "hb",
                                            "pairs": [{"question": "q", "answer": "a"},
                                                      {"question": "q2", "answer": "a2"}]},
                         "iters": 30, "lora_rank": 4, "lora_alpha": 8}},
        ]
        for j in jobs:
            await ws.send(json.dumps(j))
        async for raw in ws:
            msg = json.loads(raw)
            if msg["type"] == "result":
                hub_out["results"][msg["id"]] = msg
                hub_out["welcome"] = True
                if set(hub_out["results"]) == {"j1", "j2", "j3", "j4"}:
                    break
            elif msg["type"] == "event":
                hub_out["events"].append(msg)

    server = await websockets.serve(hub_handler, "127.0.0.1", 0)
    hub_port = server.sockets[0].getsockname()[1]
    hub_url = f"ws://127.0.0.1:{hub_port}/companion/ws"

    try:
        companion = Companion(hub_url, "test-pair", "self-test",
                              api=f"http://127.0.0.1:{api_port}", start_backend=False,
                              poll_interval=0.05, deadline_s=5)
        rc = await asyncio.wait_for(companion.run(), timeout=30)
        assert rc == 0, f"session rc={rc}"
        res = hub_out["results"]
        assert res["j1"]["ok"] and res["j1"]["data"]["capabilities"]["python"], "j1 status"
        assert res["j2"]["ok"] and res["j2"]["data"]["run_id"] == 7, "j2 train"
        assert res["j4"]["ok"] and res["j4"]["data"]["run_id"] == 7, "j4 bridge train"
        assert not res["j3"]["ok"], "unknown kind rejected"
        assert state["runs_seen"] == 2, "two runs submitted (j2 + j4)"
        assert state["datasets_created"] == 1, "j4 materialized one dataset"
        assert state["pairs_seen"] == 2, "j4 posted two QA pairs"
        assert any(e["stage"] == "materializing" for e in hub_out["events"]), "j4 materializing event"
        loss_events = [e for e in hub_out["events"] if e["stage"] == "loss" and "data" in e]
        assert loss_events, "j4 streamed loss points"
        points = loss_events[0]["data"]["points"]
        assert points and "step" in points[0] and "loss" in points[0], "loss points have step/loss"
        # j4's run body must carry the hyperparameters it received.
        j4_body = next(b for b in state["run_bodies"] if b.get("lora_rank") == 4)
        assert j4_body["lora_alpha"] == 8 and j4_body["iters"] == 30, "j4 hyperparameters forwarded"
        assert j4_body["dataset_id"] == 42, "j4 trained on the materialized dataset"

        rejected = Companion(hub_url, "wrong-token", "self-test",
                             api=f"http://127.0.0.1:{api_port}")
        rc2 = await asyncio.wait_for(rejected.run(), timeout=15)
        assert rc2 == 2, f"bad token rc={rc2}"
        print("SELF-TEST PASS — handshake, status, train (events + result), "
              "bridge handoff (materialize + hyperparams + loss stream), "
              "unknown-kind rejection, bad-token exit")
        return 0
    finally:
        server.close()
        await server.wait_closed()
        api.shutdown()


def main() -> int:
    parser = argparse.ArgumentParser(description="llmtuner companion (S24 skeleton)")
    parser.add_argument("--hub", default=os.environ.get("LLMTUNER_HUB", ""),
                        help="Hub WebSocket URL, wss://... (env LLMTUNER_HUB)")
    parser.add_argument("--token", default="",
                        help="Pairing token; prefer env LLMTUNER_PAIRING_TOKEN (avoids shell history)")
    parser.add_argument("--name", default=platform.node() or "companion", help="Companion display name")
    parser.add_argument("--api", default=API_DEFAULT, help="Local backend base URL")
    parser.add_argument("--ollama-base", default=OLLAMA_DEFAULT, help="Ollama base URL")
    parser.add_argument("--no-start-backend", action="store_true",
                        help="Never auto-start uvicorn; assume `llmtuner up` already ran")
    parser.add_argument("--self-test", action="store_true",
                        help="Run the in-process fake hub/API round-trip and exit")
    args = parser.parse_args()

    if args.self_test:
        return asyncio.run(self_test())

    token = args.token or os.environ.get("LLMTUNER_PAIRING_TOKEN", "")
    if not args.hub:
        parser.error("--hub (or LLMTUNER_HUB) is required unless --self-test")
    if not token:
        parser.error("a pairing token is required (--token or LLMTUNER_PAIRING_TOKEN); "
                     "S25 (#28) will mint scoped tokens from the web shell")

    companion = Companion(args.hub, token, args.name, api=args.api,
                          ollama_base=args.ollama_base, start_backend=not args.no_start_backend)
    try:
        return asyncio.run(companion.run())
    except KeyboardInterrupt:
        asyncio.run(companion.close())
        log("stopped")
        return 0


if __name__ == "__main__":
    sys.exit(main())
