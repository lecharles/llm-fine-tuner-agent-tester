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
| S8 | 09-22 | Tmux lanes: service-token auth (`API_SERVICE_TOKENS`), `GET /api/status`, `docs/TMUX-LANES.md` with per-lane curl | backend/, docs/ | - | TODO |
| S9 | 09-23 | Pytest suite: auth/me regression, env precedence, ladder fakes, local_server fakes, splash render | tests/ | - | TODO |
| S10 | 09-24 | CI: GitHub Actions (compile, pytest, frontend build) + README badge | .github/ | - | TODO |
| S11 | 09-25 | Train page: live loss curve (parse train.log → `/api/training-runs/{id}/losses` → tiny chart) | backend/, frontend/ | - | TODO |
| S12 | 09-26 | Dataset import: CSV/JSONL upload → Q&A pairs (endpoint + UI) | backend/, frontend/ | - | TODO |
| S13 | 09-27 | Compare: hosted-column model pickers + list installed Ollama models as optional column | frontend/, backend/ | - | TODO |
| S14 | 09-28 | Docs: README rewrite, screenshots pass, demo run-through v2 | README.md, docs/ | - | TODO |
| S15 | 09-29 | Shared-instance hardening: signup rate limit, refuse local_mode on non-loopback bind, credential rotation doc | backend/ | - | TODO |
| S16 | 09-30 | v0.1.0: version tag, release notes, final E2E + summary | repo | • | TODO |


## Hotfix inserts (dated ahead of the train)

| S# | DATE | Slice | Scope | MAC | STATUS |
|----|------|-------|-------|-----|--------|
| H1 | 09-15 | #1 VPS login 401 root cause found: the stale :8090 backend process (started 09-14 20:25) hung browser-shaped POSTs carrying an `Origin:` header; plain curl omitted Origin and succeeded, which matched "works via curl, fails in browser". Restarted from current HEAD (pid 2600030+): form login now returns 200 in ~0.24s **with and without** Origin. Remaining: Carlos browser check with normal hard refresh, then close | backend/ | - | AWAIT BROWSER VERIFY |
| H2 | 09-15 | #20 VPS keepalive shipped early: `scripts/keepalive.sh` (check/start/stop/status, auto-restart on failed /health probe, logs to /tmp/llmtuner-keepalive.log) installed in hermes crontab every 10 min with flock guard | scripts/, deploy/ | - | DONE |
| H3 | 09-15 | #42 Training failures are silent: capture `Exception as e` in `backend/training/runner.py`, persist error text + log tail on the run (new column + Alembic migration), surface in GET status and the Train UI, and add a preflight on start (425 "training runs on the Mac app only") when MLX is unavailable. Include the :8090 login-stall A/B check from H1 in the same pass. **Shipped 09-15 16:4x UTC:** migration 3b7c1d9f4a2e applied on :8090; verified POST -> 425 with plain message and no doomed run; seeded run #1 failed with RuntimeError + traceback persisted and visible via GET; login A/B re-check 7.5ms with Origin. Remaining: Carlos eyeballs the red error box on run #1 in the Train UI | backend/, frontend/ | - | AWAIT BROWSER VERIFY (UI) |
| H4 | 09-15 | #43 compare: 150-word answer cap on all four columns (single ANSWER_CAP system prompt in routers/chat.py); #44 quickstart iters guidance (10-20 smoke, 200-400 recommended) | backend/, docs/ | - | DONE (Mac verify pending) |

## October extension (Phase 5 polish, then Phase 6)

| S# | DATE | Slice | Scope | MAC | STATUS |
|----|------|-------|-------|-----|--------|
| S17 | 10-01 | Theme pass 1: theme.css foundation, cleaner status labels, nicer iters input | frontend/ | - | TODO |
| S18 | 10-02 | Theme pass 2: ConfirmDialog replacing temp no-confirm delete, VU-meter loading indicator | frontend/ | - | TODO |
| S19 | 10-05 | Accessibility: WCAG AA contrast, alt text, link-based navigation audit | frontend/ | - | TODO |
| S20 | 10-06 | Logged-in user display via GET /api/auth/me + small user menu (Linear-style) | frontend/ | - | TODO |
| S21 | 10-07 | Deploy web shell online: public instance plan, docs, and first deploy | deploy/ | - | TODO |
| S22 | 10-08 | Phase 6 ADR: hybrid (web shell + local companion) vs full local-first, decision doc | docs/ | - | TODO |
| S23 | 10-09 | macOS installer: one command or one file placing the local runtime | install/ | • | TODO |
| S24 | 10-12 | Local companion: skeleton that receives web-app requests and drives train/fuse/export/serve | companion/ | • | TODO |
| S25 | 10-13 | Opt-in bridge: explicit permission prompt, scoped and revocable hardware access | backend/, frontend/ | • | TODO |
| S26 | 10-14 | Data model split: local artifacts stay on device, hosted keeps account + metadata only | backend/ | • | TODO |
| S27 | 10-15 | Generation UX: auto-fill use-case prompt from dataset name/description | backend/, frontend/ | - | TODO |
| S28 | 10-16 | Compare: parallelize four-way fan-out instead of sequential calls | backend/ | - | TODO |

October backlog (unscheduled, labeled in GitHub): training error explainer · public/private sharing + owner-or-public auth · advanced hyperparameter panel · training-run history/visibility · brand + light/dark pass · in-app guides · more model families · API Agents / API Infrastructure repo extraction · platform expansion (React Native, native macOS, Swift).

Gate G1 (demo) sits at S4 so the desktop work rides on a proven loop; MAC
slices (S2, S5–S7, S16) are pushed by the lane but verified by Carlos on the
Mac after `git pull` — each lists its checks in the commit body.
