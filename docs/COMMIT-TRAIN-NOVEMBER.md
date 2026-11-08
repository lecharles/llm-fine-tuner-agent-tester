# Commit Train — November 2026 (ARMED)

Status: **armed 2026-11-06** — Carlos gave the GO in the LC+H Subs thread
("we need to commit every single day... can we get back on track?"). All rows
S46–S74 flipped `DRAFT → TODO`; the lane burns the backlog oldest-first.
The lane only implements rows marked TODO whose DATE is the previous calendar
day (UTC) or earlier — same scheduling as October. Today's rows stay reserved
for the nightly hotfix slot and manual work.

Theme for the month: **convert the Mac-verify debt into v0.2.0 confidence** —
restart + TLS + operator hygiene, the Phase 6 hybrid bridge going end-to-end,
and the deferred quality backlog — while the lane keeps the one-commit-per-day
streak (11-01 was the v0.1.1 close-out; daily rows resume 11-02).

|| S# | DATE | Slice | Scope | MAC | STATUS |
|----|------|-------|-------|-----|--------|
| S46 | 11-02 (Mon) | Backup + restore recipe: `sqlite3 .backup` cron on :8090 DB, tested restore drill, `docs/BACKUP.md` | scripts/, deploy/ (needs the chown from Carlos first — else docs-only) | - | DONE 2026-11-06 (morning run) — `scripts/backup_db.sh` (online backup API, integrity-checks every snapshot, rotates newest 14, 0600/0700), cron installed (daily 04:00 UTC, flock-guarded, logged), restore drill PASS (snapshot → scratch restore → integrity ok + row counts match live DB on all 10 tables); deploy/ half skipped per docs-only fallback (chown still pending) |
| S47 | 11-03 | HTTPS at the edge: self-signed → Let's Encrypt plan for :8090 shell (nginx/caddy decision doc + certbot lane script, no secrets in repo) | deploy/, docs/ | - | DONE 2026-11-06 (morning run) — `docs/EDGE-TLS.md`: A) Caddy vs B) nginx+certbot matrix, decision **Caddy** (owns the cert lifecycle), phased 0→3 plan w/ rollback + loopback-rebind; `scripts/tls_selfsigned.sh` (SAN'd self-signed pair to ~/.llmtuner/tls 600 — run ok, Feb-2029 expiry) + `scripts/tls_certbot.sh` (webroot→standalone, key never leaves /etc/letsencrypt, tested clean-fail w/o certbot); no secrets in repo; deploy/ half blocked by root ownership (docs/ scripts/ carry the load — Carlos chown still pending) |
| S48 | 11-04 | Verify checklist 1: turn the 10 pending Mac recipes into `docs/MAC-VERIFY.md` — one row per slice, exact commands, expected output, date-verified column for Carlos to tick | docs/ | • | DONE 2026-11-06 — `docs/MAC-VERIFY.md`: 10-slice board + recipes rebuilt verbatim from source commits (e0070ea, 2eb9b32, 0d2a2a5, 01d66cf, aa749ac, f42a8de, 5ae26cf, c81bf5b, fb7579e) with S45 tag checks folded into #4; tick columns live. Run order: 1→3 one sitting, 4 big E2E, 5 clean-machine, 6→8 chain, 9–10 spikes. |
| S49 | 11-05 | Companion bridge 1: pairing token mint UI (web) → paste into `llmtuner companion --pair` (CLI), hub-side `POST /api/bridge/pair` (already gated by S25 consent) | backend/, frontend/, cli/ | • | DONE 2026-11-07 — `POST /api/bridge/pair` (token in body only, no JWT — it IS the consent proof; unknown vs revoked share one 401 wording; per-peer sliding window 12/min on failures, success clears it, 429+Retry-After; never re-echoes the token); `llmtuner companion --pair --hub URL` mints nothing but redeems: hidden getpass paste (or piped stdin), pre-flight POST, grant summary printed, pair saved to `~/.llmtuner/pair.json` 0600 (token out of argv/`ps`/history); `llmtuner companion` dials via companion.py with env token; `--status` masks token tail-only; Bridge.tsx pairing sheet now leads with the copyable `llmtuner companion --pair` command + raw-env fallback. 134 backend tests pass (11 new in test_pair_s49.py), tsc clean, vite build clean. Mac recipes: **(1)** on the Mac, in the checkout: `pip install -r companion/requirements.txt`; **(2)** Bridge page → grant `air-m1` with status+train → copy token; **(3)** `PYTHONPATH=cli python -m llmtuner companion --pair --hub https://<host>` → paste → expect `✅ Paired "air-m1"` and 0600 `~/.llmtuner/pair.json`; **(4)** `llmtuner companion` → expect `paired` badge online on the Bridge page within one 15s heartbeat, then Probe → capabilities row; **(5)** revoke → socket dies on the spot, re-running the companion must fail the paste pre-flight with the one-shot 401. DONE (Mac verify pending) |
| S50 | 11-06 | Companion bridge 2: end-to-end train handoff — web "Train on this Mac" button queues a job over the WS hub, status + losses stream back (per ADR-001) | backend/, frontend/, companion/ | • | DONE 2026-11-08 (taken over by the chat lane: the 14:00 UTC train built the slice but left it uncommitted) — hub-side job registry in `backend/core/bridge.py` (`{"type":"job",kind:"train",...}` frames dialed over the existing WS hub, `JobRecord` + `_RESULTS` futures, `_prune_jobs`, `_fail_pending_jobs` flips a peer's pending jobs on revoke/disconnect); `companion/companion.py` executes train via the app's own `training.runner` on the Mac, streams loss back in bounded 80-point chunks (S50) so the 1 MiB ws cap is never at risk; web `Train.tsx` "Train on this Mac" button + live job card, `GET /api/bridge/jobs` + `/jobs/{id}` for owner polling (no request held open for hours), `_local_dataset_from_hosted` maps a hosted dataset to the Mac's local copy. 12 new tests in `tests/test_train_s50.py` (146 green), tsc clean, vite build clean. Mac recipes: **(1)** on the Mac, pull + `pip install -r companion/requirements.txt`, re-pair per S49; **(2)** Bridge page grant must include `train`; **(3)** web → dataset → "Train on this Mac" → job card shows queued→running, loss points stream in; **(4)** kill the companion mid-job → job fails with detail, second pending job flips too; **(5)** revoke the peer → live socket dies, queued jobs fail on the spot. DONE (Mac verify pending) |
| S51 | 11-07 (Sat) | Polish: loss-curve axis labels + tooltips on Train/History charts | frontend/ | - | DONE 2026-11-08 (chat lane, same-day double burn) — `LossChart.tsx` (shared by Train live curve, Mac-job card, and History): axis titles "iteration" (bottom center) + "loss" (rotated left), third y tick at window midpoint, and per-point hover: fat r=7 invisible `.loss-hover` circles carrying native `<title>` tooltips `iter N · loss 0.0000`, theme gets `.loss-hover{fill-opacity:0}` → 0.25 on hover, cursor pointer. Dependency-free SVG kept. tsc clean, vite build clean. |
| S52 | 11-08 (Sun) | Tests: companion protocol unit tests on VPS (hello/welcome/pairing/auth-error frames vs fake hub — extend the S24 self-test into pytest) | tests/, companion/ | - | TODO |
| S53 | 11-09 | Library 2: public dataset detail read-only view + owner profile line (builds on S31/S32) | backend/, frontend/ | - | TODO |
| S54 | 11-10 | passlib retirement: replace CryptContext with direct bcrypt (unpin bcrypt 4.0.1), keep hash-compat with existing users rows; filelock bump past 4.2.1 if pipenv relock works by then | backend/ | - | TODO |
| S55 | 11-11 | Ops hygiene: `:8090` restart runbook in `docs/PUBLIC-INSTANCE.md` + post-restart verification checklist (CSP headers live, api_agents boot, keepalive interaction) | deploy/, docs/ | - | TODO |
| S56 | 11-12 | Datasets 3: dedupe + merge QA pairs across datasets (endpoint + UI) | backend/, frontend/ | - | TODO |
| S57 | 11-13 (Sat) | Docs: `docs/GITHUB-ISSUES.md` refresh — reconcile #1–#44 states, close-out the H1/H3 browser-verify issues that Carlos already signed | docs/ | - | TODO |
| S58 | 11-14 | Compare 3: side-by-side scoring — thumbs per column + persisted session scores, leaderboard on the run card | backend/, frontend/ | - | TODO |
| S59 | 11-15 | Train queue: serialize concurrent runs per user (409 on second start), queue position in status payload | backend/ | - | TODO |
| S60 | 11-16 (Sun) | Tests: auth throttle + CSP regressions extended (XSS-ish payload through login, header presence on SPA fallback + 404 + 429 responses) | tests/ | - | TODO |
| S61 | 11-17 | Export 1: dataset export (JSONL + sharegpt shapes) endpoint + download button | backend/, frontend/ | - | TODO |
| S62 | 11-18 | Model serving 1: `llmtuner serve` — Ollama Modelfile generation for fused models + import smoke | cli/, backend/ | • | TODO |
| S63 | 11-19 | Week wrap 1: Mac-verify checkpoint #2 — fix whatever S48/S50 surfaced (lane picks the follow-up diffs) | repo | - | TODO |
| S64 | 11-20 (Fri) | Settings page: account (display name, password change), JWT/session info, bridge permission list + revoke | backend/, frontend/ | - | TODO |
| S65 | 11-21 (Sat) | Guides 2: contextual hints on Library/History/Settings (reuse S30 pattern) | frontend/ | - | TODO |
| S66 | 11-22 (Sun) | CI polish: pytest timing budget assertion + artifact upload for frontend build (no more than a badge) | .github/ | - | TODO |
| S67 | 11-23 | Search 1: dataset + QA-pair full-text search on SQLite FTS5 (migration + endpoint) | backend/ | - | TODO |
| S68 | 11-24 | Search 2: search UI in Datasets + Command-K palette in the shell | frontend/ | - | TODO |
| S69 | 11-25 | Metrics: request-latency log lines + `/api/status` carrying p50/p95 from in-memory window (no new deps) | backend/ | - | TODO |
| S70 | 11-26 (Thu) | Mac-verify checkpoint #3 — lane consumes S62 `serve` feedback + any installer fixes | cli/, install/ | • | TODO |
| S71 | 11-27 (Fri) | Onboarding: first-run dataset seed (10-pair demo) + welcome CTA wired to quickstart iters guidance (H4) | backend/, frontend/ | - | TODO |
| S72 | 11-28 (Sat) | Tests: library/visibility fuzz pass (random principal × endpoint matrix, 404-no-leak invariant from S31) | tests/ | - | TODO |
| S73 | 11-29 (Sun) | Docs: QUICKSTART + DEMO v3 refresh for the bridge flow (web → Mac train → results), screenshots after restart | docs/ | • | TODO |
| S74 | 11-30 | Month close: v0.2.0-rc tag + notes, November retro, December draft | repo, docs/ | • | TODO |

Explicitly deferred past November unless hotfix-inserted: React Native Expo
prototype (gate on #25 sign-off first, per S42 matrix), Swift menu-bar shell
(gate on S25 end-to-end, per S43 matrix), Postgres migration, multi-user
training quota beyond S59's per-user serialization.

Standing rules unchanged: one focused diff per row, Stay-in-Scope, py_compile +
`import main` + pytest for backend touches, `npm run build` for frontend
touches, MAC rows end with numbered Mac recipes and `DONE (Mac verify
pending)`, and **commit immediately when verification passes** (October lesson:
interrupted runs leave dirty trees).
