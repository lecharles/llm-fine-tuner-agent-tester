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

Backend changes — restart the app:

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
