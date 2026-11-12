# Public Instance — the web shell, online

S21 (issue #24): "Deploy web shell online: public instance plan, docs, and first
deploy." Training stays local (Apple Silicon / MLX requirement); everything else —
signup/login, datasets, generation ladder, compare, the run-status pages — runs
on the VPS.

> Placement note: this doc was scheduled under `deploy/` (S21 scope), but on the
> VPS `deploy/` is root-owned (since the S3 sudo install) and the lane user
> `hermes` can't write there. Moving it to `docs/` keeps the lane unblocked;
> after `sudo chown hermes:hermes deploy/` the plan can be relocated to
> `deploy/PUBLIC-INSTANCE.md` at zero cost.

**Live URL:** http://76.13.122.86:8090 — the React shell is served straight from
the FastAPI app (`backend/static_serve.py` mounts `frontend/dist`; SPA fallback
to `index.html`; `/assets/*` served as static files). No separate web server
needed.

## What's running on the VPS

| Piece | Where | Managed by |
|-------|-------|------------|
| API + web shell | uvicorn `main:app --host 0.0.0.0 --port 8090` from `backend/` | `scripts/keepalive.sh` (crontab, every 10 min, flock-guarded; auto-restarts on failed `/health`) |
| Env | `/home/hermes/llmtuner-vps/env` (`JWT_SECRET_KEY`, `LLMTUNER_HOME`; provider keys if/when added) — sourced by keepalive at start | manually by Carlos; **never committed** |
| Local engine | Ollama 0.34.1 + `llama3.2:1b` (S3), `OLLAMA_BASE_URL` set | systemd/cron on the box |
| UI build | `frontend/dist` (Vite output, served by the app) | rebuilt during deploys (runbook below) |

## Deploy / update runbook

Frontend-only changes — zero downtime, no restart:

```bash
cd /home/hermes/llm-fine-tuner-agent-tester
git pull origin main
cd frontend && npm run build          # add `npm ci` first if node_modules is missing
```

`static_serve.py` reads `dist/` from disk per request, so the new hashed assets go
live the moment the build lands.

Backend changes — restart the app: see the full **Restart runbook (:8090)**
below; the one-liner version is

```bash
cd /home/hermes/llm-fine-tuner-agent-tester
git pull origin main
backend/.venv-smoke/bin/python -m py_compile backend/main.py   # sanity
bash scripts/keepalive.sh stop && bash scripts/keepalive.sh check
```

Smoke after every deploy (all three must pass):

```bash
curl -sf http://76.13.122.86:8090/health                     # {"status":"ok",...}
curl -s http://76.13.122.86:8090/ | grep -o 'assets/[^"]*'   # new asset hashes
curl -sf -o /dev/null -w '%{http_code}\n' http://76.13.122.86:8090/welcome  # SPA fallback 200
```

## Restart runbook (:8090) — S55

Everything on this box is driven by `scripts/keepalive.sh` (`check|start|stop|status`)
plus one crontab line, every 10 minutes:

```
*/10 * * * * /usr/bin/flock -n /tmp/llmtuner-keepalive.lock bash /home/hermes/llm-fine-tuner-agent-tester/scripts/keepalive.sh check
```

`check` is the only self-healing path: if `/health` fails it pkills the old
process, re-sources `/home/hermes/llmtuner-vps/env`, re-launches uvicorn from
the **working tree at that moment**, and logs `recovered` / `STILL DOWN after
restart` to `/tmp/llmtuner-keepalive.log` (which is also the app's stdout —
uvicorn's own startup/access lines land there). The `flock -n` guard means a
tick landing mid-restart is a no-op, never a double-launch.

**Know the interactions before you touch it:**

- `stop` alone is temporary. The next cron tick (≤ 10 min) will treat the
  stopped instance as DOWN and bring it back with whatever the checkout
  contains. Intentional maintenance window = `stop`, do the work, then
  `check`/`start` yourself instead of waiting for the tick.
- `stop` + `check` back-to-back IS the restart: `check` sees DOWN, relaunches,
  sleeps 6 s, and reports. Expect `recovered` in the log within ~10 s.
- A failed boot does not roll back anything — it leaves the box DOWN with an
  `ImportError`/traceback at the tail of the log, and each cron tick retries
  the same broken tree. Read the log, then apply the rollback below.

### Procedure

1. **Preflight (both must be green before you stop anything):**

   ```bash
   cd /home/hermes/llm-fine-tuner-agent-tester
   git pull origin main
   git status --porcelain          # must be empty — never deploy a dirty tree
   backend/.venv-smoke/bin/python -m py_compile backend/main.py
   backend/.venv-smoke/bin/python -m pytest tests -q    # all green
   ```

   `pytest` runs against `.venv-smoke`, the same interpreter as the live app:
   a green suite means the *new* code boots in the *live* venv. (Heads-up:
   the suite executes in-process with TestClient; if you edit env vars, use a
   throwaway, not `/home/hermes/llmtuner-vps/env`.)

2. **Restart:**

   ```bash
   bash scripts/keepalive.sh stop    # -> "stopped"
   bash scripts/keepalive.sh check   # -> relaunches; "recovered" in the log
   ```

3. **Post-restart verification checklist** — every line exact, run from
   anywhere on the box. (1)–(4) are the row's three named gates plus health:

   ```bash
   bash scripts/keepalive.sh status
   # expect: UP
   ```

   ```bash
   curl -s --max-time 5 -o /dev/null -D- http://localhost:8090/ \
     | grep -i content-security-policy
   # expect (S44): content-security-policy: default-src 'self'; script-src 'self';
   #   style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self' data:;
   #   connect-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'self';
   #   form-action 'self'
   ```

   ```bash
   curl -s --max-time 5 -o /dev/null -w '%{http_code}\n' http://localhost:8090/api/status
   # expect: 401  (router booted + auth guard live; a 404 here would mean a
   #              router failed to import and the app half-booted)
   curl -s --max-time 5 http://localhost:8090/openapi.json \
     | backend/.venv-smoke/bin/python -c "import json,sys; print(json.load(sys.stdin)['info']['version'])"
   # expect: 0.1.1
   ```

   ```bash
   curl -sf http://localhost:8090/health
   # expect: {"status":"ok"}
   ```

   CSP notes: also spot-check that a 404 carries the header (`.../api/nope`)
   and that `/docs` does NOT (CDN exemption, `grep -c` → `0`). WebSockets
   (`/companion/ws`) pass the pure-ASGI middleware untouched — verify via the
   Bridge page, not curl.

4. **api_agents boot (the S41 extraction):** `api_agents` is imported by
   `routers/chat.py` and `routers/generation.py` at app import time, so a
   running process *is* the proof. Belt-and-braces for the checklist:

   ```bash
   cd backend && .venv-smoke/bin/python -c "import api_agents; print(len(api_agents.__all__), 'exports')"
   # expect: 9 exports
   ```

   (This is an interpreter check, not an in-process one — the boundary test
   `tests/test_api_agents_boundary_s41.py` runs inside the step-1 pytest gate.)

5. **Frontend freshness (when the diff touched frontend/):**

   ```bash
   curl -s http://localhost:8090/ | grep -o 'assets/[^"]*' | head -2
   # expect: the hashes printed by the last `npm run build`
   ```

### Rollback

The checkout is deploy-state: rolling back means checking out the last-known-good
commit and restarting, which takes the *code* back but NOT the DB (alembic
revisions stay applied — see `docs/` migration notes; never downgrade schema
casually).

```bash
cd /home/hermes/llm-fine-tuner-agent-tester
git checkout <last-good-sha>       # e.g. the sha recorded in the deploy note below
bash scripts/keepalive.sh stop && bash scripts/keepalive.sh check
# then re-run checklist items (1)-(4)
```

If even that won't boot, stop the cron from hammering the broken tree by
running `git checkout main` first and investigating — do not leave the box in
`STILL DOWN` retry loops (each tick logs, so the log grows; the instance stays
DOWN between ticks).

### Drift detector — is the live process older than the code?

The scary failure is silent: cron keeps a *healthy but ancient* process UP
forever, so merged backend work ships "when it restarts" — which is never.
Compare process start vs newest backend commit:

```bash
ps -eo lstart,args | grep -F "port 8090" | grep -v grep          # process start time
git log -1 --format='%cd %h %s' --date=iso -- backend/           # newest backend change
```

If the start time predates the newest backend commit (or touches
`Pipfile.lock`/deps), the live instance is stale: run the runbook. Cheap
proxy: step 3's CSP header — absent on anything older than S44 (472ac1b).
As of this writing the loop is closed manually (the commit train runs this
checklist after any backend-touching burn); automating "restart when
backend/ changed" is deliberately NOT done here — an unattended restart of a
shared box is the thing this checklist exists to prevent.

### Restart record (S55 — 2026-11-12 14:02 UTC / 06:02 PT)

First full run of this runbook. Before: live process started Sun Oct 25
07:10:56 at `fec2caa` (S32 level) — 18 days stale, predating S44 (no CSP
headers served — the drift detector caught exactly this), S50, S53, S54, S75.
Suite green first: 163 passed. `stop` → `stopped`; `check` → new pid,
`2026-11-12T14:02:55Z recovered` in the log (9 s). Checklist after: UP; CSP
line present on `/`, on a 404, absent on `/docs`; `/health` `{"status":"ok"}`;
`/api/status` 401; `/api/bridge/pair` answers 422 on malformed body (S49
router live); openapi version 0.1.1; `api_agents` 9 exports; `/welcome` 200.
This restart also landed S54's runtime swap (bcrypt 5.0.0, filelock 4.2.10,
passlib gone from `.venv-smoke`) into the live process — the app booted clean
with zero passlib on the path. Rollback anchor if this regresses: `fec2caa`.

## What deliberately does NOT run here

- **Training (MLX)** — Mac-only. The API preflights with 425 "training runs on the
  Mac app only" when MLX is unavailable (H3); the UI surfaces the reason.
- **Fuse/export** — same story: local-companion territory (Phase 6, S23+).
- **Cloud generation** — works only if Anthropic/OpenAI keys exist in the VPS env;
  the free Ollama fallback covers demos otherwise.

## Security posture (today) and hardening checklist

Already in (S15/#17, S8/#11): sliding-window signup rate limit
(`SIGNUP_RATE_LIMIT_PER_HOUR`, default 1/h, 429 + Retry-After), `local_mode`
hard-refusal on non-loopback bind plus per-request loopback guard, lane
service-token auth with cross-lane 403 isolation.

Open items for Carlos (public-exposure checklist):

- [ ] HTTPS: put a Caddy or nginx reverse proxy in front of :8090 with a real
      domain + Let's Encrypt; then rebind uvicorn to `127.0.0.1` so only the proxy
      is public. Until then the instance speaks plain HTTP — do not put secrets in
      the web UI from an untrusted network.
- [ ] Firewall: `ufw` allow only 22/80/443 once the proxy is up (retire public 8090).
- [ ] Rotate `JWT_SECRET_KEY` and any lane tokens before a wider invite
      (recipes in `docs/CREDENTIALS.md`).
- [ ] Decide the public signup policy: keep the 1/h rate limit vs invite codes.
- [ ] Browser check: load http://76.13.122.86:8090 in a normal browser, hard
      refresh, sign up → dataset → generate → compare (that closes #24).

## First deploy record (S21 — 2026-10-09 14:0x UTC / 07:0x PT)

- Tree at `08c935f`; UI commit level `e8e01e1` (S20). `npm run build` green:
  `dist/assets/index-Bjh74eHg.js` (288.6 kB, gzip 88.1 kB) +
  `dist/assets/index-NAaW1btf.css` (24.3 kB), 1803 modules, ~0.6s.
- Backend untouched by this slice; fresh `import main` smoke OK on
  `backend/.venv-smoke`.
- Live at first-deploy time: `/health` 200, `/` 200 with `<title>LLM Tuner</title>`
  and exactly the freshly built asset hashes — verified via localhost **and** the
  public IP 76.13.122.86:8090; keepalive reports UP.
- Remaining from "first deploy": the browser-side checklist above. Needs Carlos's
  eyeballs, so #24 stays open until he signs off.
