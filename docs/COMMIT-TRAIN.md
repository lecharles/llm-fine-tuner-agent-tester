# Commit Train — daily slices, Sept 15 → Oct 31

Carlos rule (10-05): at least one commit every calendar day; the train now runs through 10-31 (S45) with weekend rows included.

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
| S2 | 09-16 | `llmtuner app`: floating browser-app window (Chrome `--app`), falls back to default browser; `--size` flag | cli/ | • | CODED — AWAIT MAC VERIFY |
| S3 | 09-17 | VPS generation: install Ollama on server, pull a 1B model, set `OLLAMA_BASE_URL`, smoke `generate` | deploy/ | - | DONE 2026-09-17 — Ollama 0.34.1, llama3.2:1b (1.3GB), OLLAMA_BASE_URL set, ladder smoke ok |
| S4 | 09-18 | Welcome/motivation page (route `/welcome` + sidebar entry); gate G1 demo script `docs/DEMO.md` | frontend/, docs/ | - | DONE 2026-09-18 — `/welcome` lands + sidebar entry, `docs/DEMO.md` G1 script; `npm run build` green |
| S5 | 09-19 | Icon pipeline `scripts/make_app_icon.sh`: favicon.svg → AppIcon.icns (sips/iconutil) | scripts/ | • | DONE (Mac verify pending) |
| S6 | 09-20 | `llmtuner bundle`: generate `LLM Tuner.app` (Info.plist, launcher, icon) so app name + Dock identity are native | cli/, scripts/ | • | DONE (Mac verify pending) |
| S7 | 09-21 | Menu-bar extra `llmtuner menubar` (rumps): status dot, open window, start/stop, quit; optional dep | cli/ | • | DONE (Mac verify pending) |
| S8 | 09-22 | Tmux lanes: service-token auth (`API_SERVICE_TOKENS`), `GET /api/status`, `docs/TMUX-LANES.md` with per-lane curl | backend/, docs/ | - | DONE 2026-09-22 — lane:token service auth, /api/status identity, lane delete 403 + isolation smoke green |
| S9 | 09-23 | Pytest suite: auth/me regression, env precedence, ladder fakes, local_server fakes, splash render | tests/ | - | DONE 2026-09-24 — 37 tests green in ~5s (backend/.venv-smoke/bin/python -m pytest tests -q) |
| S10 | 09-24 | CI: GitHub Actions (compile, pytest, frontend build) + README badge | .github/ | - | DONE 2026-09-25 — ci.yml (py3.12: compileall, `import main` smoke, pytest; node22: npm ci + build) + README badge; suite green locally 37/37 |
| S11 | 09-25 | Train page: live loss curve (parse train.log → `/api/training-runs/{id}/losses` → tiny chart) | backend/, frontend/ | - | DONE 2026-09-26 — runner streams train.log live; tolerant parser + GET /api/training-runs/{id}/losses (auth'd, 404 on foreign run, [] before first log line); Train page polls it with the status tick and renders a dependency-free SVG curve; py_compile + `import main` + pytest 37 green + `npm run build` green |
| S12 | 09-26 | Dataset import: CSV/JSONL upload → Q&A pairs (endpoint + UI) | backend/, frontend/ | - | DONE 2026-09-27 — POST /api/datasets/{id}/qa-pairs/upload (multipart CSV/JSONL/TSV, alias headers, 2MB/5000-pair caps, 400 with reason); DatasetDetail "Import from file" picker appends pairs live; py_compile + `import main` + OpenAPI route check + parser smoke + pytest 37 green + `npm run build` green |
| S13 | 09-27 | Compare: hosted-column model pickers + list installed Ollama models as optional column | frontend/, backend/ | - | DONE 2026-09-28 — OpenAI/Anthropic columns got per-column model dropdowns (defaults unchanged; gpt-4o, gpt-5.5, claude-sonnet-5 offered), sent to the session on create; new GET /api/compare/ollama-models lists installed Ollama models and picking one adds a fifth "ollama" column via session compare_ollama_model (migration 5c8f2a1e9d34); py_compile + `import main` + OpenAPI route + ollama /api/tags smoke (llama3.2:1b) + pytest 37 green + `npm run build` green |
| S14 | 09-28 | Docs: README rewrite, screenshots pass, demo run-through v2 | README.md, docs/ | - | DONE 2026-09-29 — README rewritten (#16: pitch/install Mac+VPS/quickstart/screenshots/docs map), fresh headless captures docs/screenshots/00-login+01-signup from live :8090, `docs/SCREENSHOTS.md` inventory + re-shoot recipes (6 legacy shots still stale pending a Mac session), DEMO v2 with Mac+VPS variants |
| S15 | 09-29 | Shared-instance hardening: signup rate limit, refuse local_mode on non-loopback bind, credential rotation doc | backend/ | - | DONE 2026-09-30 — #17: sliding-window signup limiter (per-IP, SIGNUP_RATE_LIMIT_PER_HOUR default 1/h, 429 + Retry-After, failed attempts burn the window); local_mode hard-refusal at startup (`--host 0.0.0.0` + LOCAL_MODE=true → RuntimeError, loopback/default fine) plus a per-request guard 403ing non-loopback peers at runtime (/health stays open for monitors); `docs/CREDENTIALS.md` rotation recipes (JWT, lane tokens, provider keys, password resets). py_compile + `import main` + pytest 46 green (9 new in tests/test_shared_hardening.py); no frontend changes |
| S16 | 09-30 | v0.1.0: version tag, release notes, final E2E + summary | repo | • | DONE (Mac verify pending) 2026-10-01 — #18: v0.1.0 tagged, docs/RELEASE-v0.1.0.md, version surfaced (CLI --version, FastAPI, package.json); VPS half of DEMO B lane-checked; Mac Script A + desktop extras pending Carlos |


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
| S17 | 10-01 | Theme pass 1: theme.css foundation, cleaner status labels, nicer iters input | frontend/ | - | DONE 2026-10-02 — #21: status badges sentence-cased via shared `displayStatus` (Train run, Models, Datasets/DatasetDetail source, GetStarted "Ready"); iters input = −/+ stepper (±50, clamped 1–5000) + preset chips (20 smoke · 300 recommended · 1000 full run) with active state; theme.css gains the S17 stepper/chip section (token-driven, light+dark). `tsc -b && vite build` green |
| S18 | 10-02 | Theme pass 2: ConfirmDialog replacing temp no-confirm delete, VU-meter loading indicator | frontend/ | - | DONE 2026-10-03 — #21: destructive-path audit clean — `window.confirm` was already retired in July's dataset REST work and both UI DELETEs (dataset, QA pair) route through `ConfirmDialog`, verified no temp/no-confirm delete remains; shipped the new shared `VuMeter` loader (pure-CSS EQ bars on `currentColor`, aria-hidden, reduced-motion freeze) wired into the Datasets / Dataset detail / Models "Loading…" rows and the Compare columns (retired `.tdot`); `tsc -b && vite build` green |
| S19 | 10-05 | Accessibility: WCAG AA contrast, alt text, link-based navigation audit | frontend/ | - | DONE 2026-10-05 — #21: measured every text/accent token pair in both themes (scripted WCAG math); light-mode success/warning/danger/hosted/guide deepened to AA (were 3.3–4.3:1), new `--primary-strong` button fill (white label 5.3:1 dark / 7.3:1 light) + `--focus-ring` token (≥6:1); global `:focus-visible` outline, skip-to-content link + `#main-content` landmark (`tabIndex=-1`); Welcome CTAs are now router `<Link>`s; all form labels associated via htmlFor/id (Login/Signup/Train/QAPair/DatasetForm), `role="alert"` on 9 error paragraphs, hidden file input made focusable (`sr-file-input`), decorative icons aria-hidden; zero `<img>` in app (LossChart svg already labeled). `tsc -b && vite build` green |
| S20 | 10-06 | Logged-in user display via GET /api/auth/me + small user menu (Linear-style) | frontend/ | - | TODO |
| S21 | 10-07 | Deploy web shell online: public instance plan, docs, and first deploy | deploy/ | - | TODO |
| S22 | 10-08 | Phase 6 ADR: hybrid (web shell + local companion) vs full local-first, decision doc | docs/ | - | TODO |
| S23 | 10-09 | macOS installer: one command or one file placing the local runtime | install/ | • | TODO |
| S24 | 10-12 | Local companion: skeleton that receives web-app requests and drives train/fuse/export/serve | companion/ | • | TODO |
| S25 | 10-13 | Opt-in bridge: explicit permission prompt, scoped and revocable hardware access | backend/, frontend/ | • | TODO |
| S26 | 10-14 | Data model split: local artifacts stay on device, hosted keeps account + metadata only | backend/ | • | TODO |
| S27 | 10-15 | Generation UX: auto-fill use-case prompt from dataset name/description | backend/, frontend/ | - | TODO |
| S28 | 10-16 | Compare: parallelize four-way fan-out instead of sequential calls | backend/ | - | TODO |

## Month-close extension (daily through 10-31, from the October backlog)

Carlos rule 10-05: at least one commit **every calendar day** — weekend rows
are scoped VPS-safe (docs/tests/polish) so the lane never idles. Slices pull
from the October backlog below; split items get an explicit second row.

| S# | DATE | Slice | Scope | MAC | STATUS |
|----|------|-------|-------|-----|--------|
| S29 | 10-10 (Sat) | Training error explainer: map common MLX/Ollama/QLoRA failure strings to human cause + fix, shown under the failed run | backend/, frontend/ | - | TODO |
| S30 | 10-11 (Sun) | In-app guides 1: contextual help bubbles on Train + Dataset detail (reuse S17 hint pattern) | frontend/ | - | TODO |
| — | 10-12 → 10-16 | (existing rows S24–S28 above) | | | |
| S31 | 10-17 (Sat) | Public/private sharing 1: visibility field on datasets/models, owner-or-public authz | backend/ | - | TODO |
| S32 | 10-18 (Sun) | Sharing 2: share toggle UI + public library page | frontend/ | - | TODO |
| S33 | 10-19 | Advanced hyperparameter panel 1: LoRA rank/alpha + learning rate in train config (backend) | backend/ | - | TODO |
| S34 | 10-20 | Hyperparameter panel 2: UI section with validated defaults + tooltips | frontend/ | - | TODO |
| S35 | 10-21 | Training-run history 1: runs list (dataset, base model, iters, final loss) | backend/ | - | TODO |
| S36 | 10-22 | Run history 2: history page + log viewer + loss replay per run | frontend/ | - | TODO |
| S37 | 10-23 | More model families 1: phi-4 + gemma-3 recipes in the local registry, fallback-ladder entries | backend/, docs/ | - | TODO |
| S38 | 10-24 (Sat) | More model families 2: registry tests + ladder fakes for new families | tests/ | - | TODO |
| S39 | 10-25 (Sun) | Brand + light/dark pass: empty states, icon consistency sweep, screenshot refresh | frontend/, docs/ | - | TODO |
| S40 | 10-26 | API Agents repo extraction: boundary map + ADR (what lives where, import cuts) | docs/ | - | TODO |
| S41 | 10-27 | API Infrastructure extraction 1: provider-client layer split into its own package/module | backend/ | - | TODO |
| S42 | 10-28 | Platform expansion 1: React Native shell spike notes + feasibility matrix | docs/ | • | TODO |
| S43 | 10-29 | Platform expansion 2: native macOS (Swift) companion spike notes | docs/ | • | TODO |
| S44 | 10-30 | Perf + security sweep: dependency audit, list-query indexes, CSP/rate-limit pass | backend/ | - | TODO |
| S45 | 10-31 (Sat) | Month close: v0.1.1 tag + notes, October retro, November train draft | repo, docs/ | • | TODO |

October backlog: all items are now scheduled as S29–S45 above (was: training
error explainer · sharing · hyperparameter panel · run history · brand pass ·
in-app guides · model families · repo extraction · platform expansion). New
unscheduled ideas land in the November train draft (S45).

Gate G1 (demo) sits at S4 so the desktop work rides on a proven loop; MAC
slices (S2, S5–S7, S16) are pushed by the lane but verified by Carlos on the
Mac after `git pull` — each lists its checks in the commit body.
