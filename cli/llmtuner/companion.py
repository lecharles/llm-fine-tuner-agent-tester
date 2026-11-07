"""S49 — `llmtuner companion`: the paste-half of the bridge pairing.

The web shell (S25 consent act) mints a one-time pairing token; this command
is where that token lands on the Mac. Flow:

    llmtuner companion --pair --hub https://host   # paste token at the prompt
    llmtuner companion                              # dial out using the saved pair

`--pair` POSTs the pasted token to `POST /api/bridge/pair` (S49 hub endpoint)
BEFORE anything dials the WS hub, so a wrong/expired/revoked token produces a
clear one-shot message instead of the companion's silent reconnect loop. A
successful redemption is persisted to `~/.llmtuner/pair.json` (0600 — this is
the only place the plaintext token is ever written, mirroring the web shell's
"shown once" promise; the server stores only its sha256).

The token is asked for with a hidden prompt (getpass) or piped on stdin for
scripted use — never as an argv flag, so it cannot show up in `ps` or shell
history. Running (`llmtuner companion` with no flag) execs the real
companion runtime (companion/companion.py, S24/S26) with the token handed over
via the LLMTUNER_PAIRING_TOKEN env var, again keeping it out of argv.

stdlib-only in this module: the redemption pre-flight must be runnable on any
machine with python (no websockets dependency), including the VPS test lane.
"""

from __future__ import annotations

import getpass
import json
import os
import platform
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

PAIR_FILE_NAME = "pair.json"


def llmtuner_home() -> Path:
    """Same rule as the backend: LLMTUNER_HOME wins over ~/.llmtuner."""
    return Path(os.environ.get("LLMTUNER_HOME") or Path.home() / ".llmtuner")


def pair_file() -> Path:
    return llmtuner_home() / PAIR_FILE_NAME


def ws_url_for(hub_base: str) -> str:
    """Map the human-entered hub URL to the companion's WS endpoint.

    Accepts https://host, https://host/, host:8090 or an explicit wss:// URL
    (passed through untouched). http -> ws, https -> wss; path is /companion/ws.
    """
    raw = (hub_base or "").strip().rstrip("/")
    if not raw:
        return ""
    if raw.startswith(("ws://", "wss://")):
        return raw if raw.endswith("/companion/ws") else raw + "/companion/ws"
    if "://" not in raw:
        raw = "https://" + raw  # bare host:port on an https-by-default web shell
    scheme = "ws" if raw.startswith("http://") else "wss"
    return f"{scheme}://{raw.split('://', 1)[1]}/companion/ws"


def _api_base(hub_base: str) -> str:
    raw = (hub_base or "").strip().rstrip("/")
    if raw.startswith(("ws://", "wss://")):
        return ("http://" if raw.startswith("ws://") else "https://") + \
            raw.split("://", 1)[1].removesuffix("/companion/ws")
    return raw


def read_pair() -> dict | None:
    try:
        return json.loads(pair_file().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def write_pair(data: dict) -> None:
    home = llmtuner_home()
    home.mkdir(parents=True, exist_ok=True)
    path = pair_file()
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    path.chmod(0o600)  # plaintext token — owner-only, like ~/.ssh/id_*


def _prompt_token() -> str:
    """Read the pasted token without echoing it. Piped stdin works for CI."""
    if not sys.stdin.isatty():
        return sys.stdin.read().strip()
    return getpass.getpass("Paste the pairing token from the Bridge page: ").strip()


def _post_pair(api_base: str, token: str, timeout: float = 15.0) -> tuple[int, dict | str]:
    req = urllib.request.Request(
        f"{api_base}/api/bridge/pair",
        data=json.dumps({"token": token}).encode(),
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode(errors="replace")
            return resp.status, _parse(raw)
    except urllib.error.HTTPError as err:
        return err.code, _parse(err.read().decode(errors="replace"))
    except (urllib.error.URLError, TimeoutError, OSError) as err:
        return 0, f"unreachable: {err}"


def _parse(raw: str):
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw[:300]


def _detail_of(body) -> str:
    if isinstance(body, dict):
        return str(body.get("detail") or json.dumps(body))[:300]
    return str(body)[:300]


def pair(hub_base: str, token: str = "") -> int:
    if not hub_base:
        print("❌ --hub is required, e.g. `llmtuner companion --pair --hub https://tuner.example`")
        return 1
    token = token or _prompt_token()
    if not token:
        print("❌ No token pasted. Grant one on the Bridge page of the web shell first.")
        return 1

    code, body = _post_pair(_api_base(hub_base), token)
    if code == 0:
        print(f"❌ Could not reach {hub_base} — check the URL and your network.\n   {_detail_of(body)}")
        return 1
    if code == 422:
        print("❌ That does not look like a pairing token (they start with 'br1-').")
        return 1
    if code == 429:
        print("❌ Too many failed pairing attempts — wait a minute, then re-paste.")
        return 1
    if code != 200 or not isinstance(body, dict) or not body.get("paired"):
        print(f"❌ Hub rejected the pairing token (HTTP {code}): {_detail_of(body)}")
        print("   Tokens are one-time: if it was already used or revoked, grant a fresh")
        print("   one on the Bridge page and paste THAT one.")
        return 1

    write_pair({
        "hub": ws_url_for(hub_base),
        "api_base": _api_base(hub_base),
        "token": token,  # plaintext lives only here, 0600, on the user's Mac
        "permission_id": body.get("permission_id"),
        "device_name": body.get("name"),
        "granted_scopes": body.get("granted_scopes") or [],
        "paired_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "hub_protocol": body.get("protocol", "llmtuner-companion/0"),
    })
    print(f"✅ Paired “{body.get('name')}” — scopes: {', '.join(body.get('granted_scopes') or []) or '(none)'}")
    print(f"   Saved to {pair_file()} (permissions 0600).")
    print("   Start the companion anytime with:  llmtuner companion")
    return 0


def status() -> int:
    data = read_pair()
    if data is None:
        print("No saved pairing. Run:  llmtuner companion --pair --hub <url>")
        return 1
    print(f"paired device : {data.get('device_name', '?')} (permission {data.get('permission_id', '?')})")
    print(f"hub           : {data.get('hub', '?')}")
    print(f"scopes        : {', '.join(data.get('granted_scopes') or []) or '(none)'}")
    print(f"paired at     : {data.get('paired_at', '?')}")
    print(f"token         : br1-…{str(data.get('token', ''))[-6:]} (stored 0600 at {pair_file()})")
    return 0


def run(hub: str = "", name: str = "", no_start_backend: bool = False) -> int:
    data = read_pair()
    if data is None and not (hub and os.environ.get("LLMTUNER_PAIRING_TOKEN")):
        print("No saved pairing. Run:  llmtuner companion --pair --hub <url>")
        return 1
    hub_url = ws_url_for(hub) if hub else str((data or {}).get("hub", ""))
    if not hub_url:
        print("❌ Nothing to dial: no saved pair and --hub missing.")
        return 1
    token = os.environ.get("LLMTUNER_PAIRING_TOKEN") or str((data or {}).get("token", ""))
    if not token:
        print("❌ No pairing token (saved pair missing and LLMTUNER_PAIRING_TOKEN unset).")
        return 1

    companion_script = Path(__file__).resolve().parent.parent.parent / "companion" / "companion.py"
    if not companion_script.exists():
        print(f"❌ companion runtime not found at {companion_script}")
        return 1

    try:
        import websockets  # noqa: F401
    except ImportError:
        print("❌ The 'websockets' package is missing — install companion deps first:")
        print("   pip install -r companion/requirements.txt")
        return 1

    argv = [sys.executable, str(companion_script), "--hub", hub_url,
            "--name", name or (data or {}).get("device_name") or platform.node() or "companion"]
    if no_start_backend:
        argv.append("--no-start-backend")
    env = os.environ.copy()
    env["LLMTUNER_PAIRING_TOKEN"] = token  # env, not argv — keeps it out of `ps`
    print(f"📡 dialing {hub_url} as “{argv[argv.index('--name') + 1]}” (Ctrl+C to stop)")
    try:
        return subprocess.run(argv, env=env).returncode
    except KeyboardInterrupt:
        print("\n👋 companion stopped")
        return 0


def companion_command(pair_flag: bool, hub: str, name: str, do_status: bool,
                      no_run: bool, no_start_backend: bool, token: str = "") -> int:
    if do_status:
        return status()
    if pair_flag:
        rc = pair(hub, token)
        if rc != 0 or no_run:
            return rc
        return run(hub, name, no_start_backend)
    return run(hub, name, no_start_backend)
