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
| S46 | 11-02 (Mon) | Backup + restore recipe: `sqlite3 .backup` cron on :8090 DB, tested restore drill, `docs/BACKUP.md` | scripts/, deploy/ (needs the chown from Carlos first — else docs-only) | - | TODO |
| S47 | 11-03 | HTTPS at the edge: self-signed → Let's Encrypt plan for :8090 shell (nginx/caddy decision doc + certbot lane script, no secrets in repo) | deploy/, docs/ | - | TODO |
| S48 | 11-04 | Verify checklist 1: turn the 10 pending Mac recipes into `docs/MAC-VERIFY.md` — one row per slice, exact commands, expected output, date-verified column for Carlos to tick | docs/ | • | TODO |
| S49 | 11-05 | Companion bridge 1: pairing token mint UI (web) → paste into `llmtuner companion --pair` (CLI), hub-side `POST /api/bridge/pair` (already gated by S25 consent) | backend/, frontend/, cli/ | • | TODO |
| S50 | 11-06 | Companion bridge 2: end-to-end train handoff — web "Train on this Mac" button queues a job over the WS hub, status + losses stream back (per ADR-001) | backend/, frontend/, companion/ | • | TODO |
| S51 | 11-07 (Sat) | Polish: loss-curve axis labels + tooltips on Train/History charts | frontend/ | - | TODO |
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
