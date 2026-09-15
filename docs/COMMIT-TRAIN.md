# Commit Train — daily slices, Sept 15–30

Rules for the automated lane:
- Implement exactly one slice per day, the one whose DATE is today (UTC).
- Commit with today's date, message prefix `feat|fix|docs|test|ci: <slice S#>`.
- Push to `main`. Never force-push. If the repo root contains `PAUSE`, stop.
- Backend changes must pass `python -m py_compile` on touched files, the repo
  test suite if present, and a fresh `import main` smoke.
- Frontend changes must pass `npm run build`.
- If a slice needs a real Mac (marked MAC), write the code, add docs, and list
  the manual verification steps in the commit body; do not claim it works.
- Update the STATUS column when done. Keep diffs focused; no drive-by refactors.

| S# | DATE | Slice | Scope | MAC | STATUS |
|----|------|-------|-------|-----|--------|
| S1 | 09-15 | Foundations: key loading, auth/me, splash, compare engines, fallback ladder | done in 53f3b71…1d56f87 | - | DONE |
| S2 | 09-16 | `llmtuner app`: floating browser-app window (Chrome `--app`), falls back to default browser; `--size` flag | cli/ | • | TODO |
| S3 | 09-17 | VPS generation: install Ollama on server, pull a 1B model, set `OLLAMA_BASE_URL`, smoke `generate` | deploy/ | - | TODO |
| S4 | 09-18 | Welcome/motivation page (route `/welcome` + sidebar entry); gate G1 demo script `docs/DEMO.md` | frontend/, docs/ | - | TODO |
| S5 | 09-19 | Icon pipeline `scripts/make_app_icon.sh`: favicon.svg → AppIcon.icns (sips/iconutil) | scripts/ | • | TODO |
| S6 | 09-20 | `llmtuner bundle`: generate `LLM Tuner.app` (Info.plist, launcher, icon) so app name + Dock identity are native | cli/, scripts/ | • | TODO |
| S7 | 09-21 | Menu-bar extra `llmtuner menubar` (rumps): status dot, open window, start/stop, quit; optional dep | cli/ | • | TODO |
| S8 | 09-22 | Team lanes: service-token auth (`API_SERVICE_TOKENS`), `GET /api/status`, `docs/TEAMOX.md` with per-lane curl | backend/, docs/ | - | TODO |
| S9 | 09-23 | Pytest suite: auth/me regression, env precedence, ladder fakes, local_server fakes, splash render | tests/ | - | TODO |
| S10 | 09-24 | CI: GitHub Actions (compile, pytest, frontend build) + README badge | .github/ | - | TODO |
| S11 | 09-25 | Train page: live loss curve (parse train.log → `/api/training-runs/{id}/losses` → tiny chart) | backend/, frontend/ | - | TODO |
| S12 | 09-26 | Dataset import: CSV/JSONL upload → Q&A pairs (endpoint + UI) | backend/, frontend/ | - | TODO |
| S13 | 09-27 | Compare: hosted-column model pickers + list installed Ollama models as optional column | frontend/, backend/ | - | TODO |
| S14 | 09-28 | Docs: README rewrite, screenshots pass, demo run-through v2 | README.md, docs/ | - | TODO |
| S15 | 09-29 | Shared-instance hardening: signup rate limit, refuse local_mode on non-loopback bind, credential rotation doc | backend/ | - | TODO |
| S16 | 09-30 | v0.1.0: version tag, release notes, final E2E + summary | repo | • | TODO |

Gate G1 (demo) sits at S4 so the desktop work rides on a proven loop; MAC
slices (S2, S5–S7, S16) are pushed by the lane but verified by Carlos on the
Mac after `git pull` — each lists its checks in the commit body.
