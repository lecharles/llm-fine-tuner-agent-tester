# LLM Tuner v0.1.0 — Release Notes

**Tag:** `v0.1.0` on `main` · **Date:** 2026-10-01 (slice S16, planned 09-30) · **Issues:** #1–#17 shipped or deferred, #18 is this release.

The v0.1.0 goal: the full loop — generate → import → train → compare — runs
end-to-end, on a Mac (local MLX) and on the shared VPS (hosted + Ollama
fallback), with tests and CI guarding it.

## What shipped

| Area | Slice | Highlights |
|------|-------|-----------|
| Foundations | S1 | Key loading, `auth/me`, splash, compare engines, generation fallback ladder (Anthropic → OpenAI → Ollama) |
| Desktop (Mac) | S2, S5–S7 | `llmtuner app` floating Chrome-app window + `--size`, icon pipeline (`make_app_icon.sh`), `llmtuner bundle` (`LLM Tuner.app`), `llmtuner menubar` (rumps) — code merged, **Mac verify pending** |
| VPS | S3, H2 | Ollama 0.34.1 + llama3.2:1b on the server, `OLLAMA_BASE_URL`, keepalive cron every 10 min |
| Web UI | S4, S11–S13 | `/welcome` landing page, live loss curve on Train, CSV/JSONL dataset import, per-column hosted model pickers + optional Ollama column |
| Team lanes | S8 | `API_SERVICE_TOKENS` lane auth, `GET /api/status`, `docs/TMUX-LANES.md` |
| Resilience | H3, H4 | Training failures surface (error text + log tail, red UI box), 425 preflight when MLX missing, ~150-word answer cap on compare |
| Hardening | S15 | Signup rate limit (1/IP/hour), `LOCAL_MODE` refuses non-loopback bind, `docs/CREDENTIALS.md` rotation recipes |
| Quality | S9, S10, S14 | Pytest suite (46 tests), GitHub Actions CI + badge, README rewrite + screenshots + demo v2 |

## Version surfaces

- `llmtuner --version` → `llmtuner 0.1.0` (source of truth: `cli/llmtuner/__init__.__version__`)
- FastAPI/openapi `/docs` header: `0.1.0` (`backend/main.py`)
- `frontend/package.json`: `0.1.0`
- Git tag: `v0.1.0`

## Verification at tag time

- `backend/.venv-smoke/bin/python -m pytest tests -q` — green
- `python -m py_compile` on all touched `.py` + fresh `import main` smoke — green
- `npm run build` in `frontend/` — green
- VPS `http://76.13.122.86:8090/health` — ok, keepalive running

## Final E2E — Mac verification pending

The **VPS half of `docs/DEMO.md` Script B** is lane-verified above. The **Mac
half (Script A)** and the desktop extras need real Apple Silicon hardware; run
them per the recipe in the S16 commit body. Until Carlos signs off, the
desktop slices (S2, S5–S7, S16) stay at `DONE (Mac verify pending)` and S16 is
not called "works on Mac".

## Deferred to v0.2 (October extension)

Theme passes (S17–S18), accessibility (S19), user menu (S20), public web
shell (S21), Phase 6 ADR + installer + companion + bridge + data split
(S22–S26), generation UX (S27), compare parallelization (S28). See
`docs/COMMIT-TRAIN.md`.

## Known issues

- H1/H3 UI: awaiting Carlos browser eyeball (login hard-refresh, red error box).
- 6 legacy screenshots stale pending a Mac capture session (`docs/SCREENSHOTS.md`).
