# GitHub Issues — Full List

All bugs, features, and infrastructure work identified during the Sept 15 demo
run-through (#1–#20, plus the same-day reports #42–#46) and the ROADMAP Phase 5/6
decomposition (#21–#41).

**Reconciled 2026-11-14 (S57 lane run)** against three sources: the live GitHub
issue state (`api.github.com/repos/lecharles/llm-fine-tuner-agent-tester/issues`,
all 46 issues), the commit-train ledgers (`docs/COMMIT-TRAIN.md`,
`docs/COMMIT-TRAIN-NOVEMBER.md`), and repo records (MAC-VERIFY board, ROADMAP
checkboxes, commit bodies). This file is the index; issue bodies live at
`https://github.com/lecharles/llm-fine-tuner-agent-tester/issues/<N>`.

## State legend

- **CLOSED (GitHub)** — already closed upstream.
- **CLOSED (signed off)** — work shipped and browser-verified; Carlos signed off
  on the H1/H3 checks (recorded on the S57 row of the November ledger). GitHub
  flip is a manual step — see *Bookkeeping* below (the lane has no issue-write token).
- **RESOLVED** — shipped by a train slice; GitHub issue still open upstream, flip pending.
- **MAC VERIFY PENDING** — code shipped and VPS-verified; the Apple-Silicon half
  waits on `docs/MAC-VERIFY.md` board #N.
- **PARTIAL / IN PROGRESS / DEFERRED / OPEN** — genuinely unfinished; the note says what remains.

## Index

| # | Title | State | Shipped in | Notes |
|---|-------|-------|-----------|-------|
| 1 | VPS login 401 despite valid credentials | **CLOSED (signed off)** | H1 (ledger `docs/COMMIT-TRAIN.md`) | Root cause was the stale :8090 process hanging browser-shaped POSTs carrying `Origin:` — NOT the original JSON-vs-form theory. Restart fixed it; form login 200 in ~0.24 s with and without Origin; Carlos browser-verified with hard refresh and signed off. GitHub flip pending (see Bookkeeping). |
| 2 | Compare: failed columns don't persist to history | RESOLVED | `1d56f87` + S75 (`a15e1ac`) | S75 added `chat_messages.status` (rev `b7d3f2a8c5e1`): failed columns persist as ⚠ rows, survive reload, and are excluded from history replay. The "column disabled after 2 fails" badge remains a ROADMAP compare-depth idea. |
| 3 | Ollama fallback doesn't auto-select a model | RESOLVED | S37 (`local_registry.py`) | 3-family recipe order (llama3.2 → phi4-mini → gemma3:4b); "fixed #3". `GENERATION_LOCAL_MODELS` override still honored. |
| 4 | Loss curve not shown in real-time | RESOLVED | S11 (+S51 polish) | train.log → `GET /api/training-runs/{id}/losses` → live dependency-free SVG on Train; axis labels + per-point tooltips in S51. |
| 5 | Compare: hosted columns can't swap for local models | RESOLVED | S13 | 5th optional "ollama" column (session `compare_ollama_model`, migration `5c8f2a1e9d34`) + hosted pickers. |
| 6 | Desktop app: `llmtuner app` floating window | MAC VERIFY PENDING | S2 (cli/) | `CODED — AWAIT MAC VERIFY` on the ledger; board recipe added by the S63 checkpoint — now **MAC-VERIFY #11** in `docs/MAC-VERIFY.md`. |
| 7 | Desktop app: menu-bar integration (rumps) | MAC VERIFY PENDING | S7 | Board #3. |
| 8 | Desktop app: icon pipeline (favicon → icns) | MAC VERIFY PENDING | S5 (`e0070ea`) | Board #1. |
| 9 | Desktop app: `.app` bundle identity | MAC VERIFY PENDING | S6 (`2eb9b32`) | Board #2. |
| 10 | Welcome/motivation page | RESOLVED | S4 (+S39) | `/welcome` + sidebar; empty-state/icon polish in S39. |
| 11 | Team lanes: service-token auth | RESOLVED | S8 | `API_SERVICE_TOKENS`, `GET /api/status`, `docs/TMUX-LANES.md`; the lane 403 rule still guards writes today (reused by S56). |
| 12 | Pytest suite | RESOLVED | S9 | 37 tests then; **176 today (~20 s)** — the original <10 s budget is exceeded by backlog growth; S66 (11-16) pins a timing-budget assertion. |
| 13 | CI: GitHub Actions | RESOLVED | S10 | `.github/workflows` compileall + `import main` + pytest + npm build; README badge. Polish = S66. |
| 14 | Dataset import: CSV/JSONL upload | RESOLVED | S12 | multipart upload endpoint + "Import from file" on Dataset detail (2 MB/5000-pair caps). |
| 15 | Compare: hosted-column model pickers | RESOLVED | S13 | gpt-4o / gpt-5.5 / claude-sonnet-5 offered; per-session model choice surfaced in UI stays a ROADMAP box. |
| 16 | Docs: README rewrite + screenshots | RESOLVED | S14 (+S39) | README rewritten; `docs/screenshots/00+01` re-shot (S39). The 6 legacy Sept-14 storyboard shots in `screenshots/` stay stale (see `docs/SCREENSHOTS.md`); S73 (11-29) refreshes after a Mac session. |
| 17 | Shared-instance hardening | RESOLVED | S15 + S44 | signup limiter, local_mode refusal, `docs/CREDENTIALS.md`, CSP headers, login throttle — all LIVE on :8090 since the S55 restart. |
| 18 | v0.1.0 release | **CLOSED (GitHub)** | `0d2a2a5` | tag v0.1.0 + notes; v0.1.1 followed (S45 `2697a48`); v0.2.0-rc scheduled as S74. |
| 19 | Commit train automation | ACTIVE (umbrella) | the lane itself | One-commit-per-day streak held since 09-16; October closed; November train ARMED 11-06 with Carlos's GO. Keep open until the S74 month close. |
| 20 | VPS keepalive cron | **CLOSED (GitHub)** | H2 | `scripts/keepalive.sh`, flock-guarded 10-min tick; runbook + drift detector documented in S55. |
| 21 | Phase 5: theme pass + styled components | RESOLVED | S17 + S18 | theme.css tokens, sentence-cased statuses, iters stepper/chips, ConfirmDialog, VuMeter. |
| 22 | Phase 5: accessibility (WCAG AA) | RESOLVED | S19 | AA contrast both themes, `:focus-visible`, skip link, label associations, `role="alert"`. |
| 23 | Phase 5: logged-in user display | RESOLVED | S20 | `UserMenu` via `/api/auth/me`, Linear-style popover. |
| 24 | Phase 5: deploy web shell online | **CLOSED (GitHub)** | S21 (`9ffec1a`) | Live at :8090; post-restart checklist (S55) re-verified health/UI/SPA/CSP. |
| 25 | Phase 6 ADR: hybrid vs local-first | OPEN — sign-off pending | S22 (ADR-001 `7373223`) | Status still **Proposed** even though Option A was implemented (S23–S26, S49–S50 all shipped hybrid). Formal sign-off gates platform expansion: S42/S43 findings land here, RN/Swift builds stay deferred until signed. |
| 26 | Phase 6: macOS installer | MAC VERIFY PENDING | S23 (`01d66cf`) | Board #5. |
| 27 | Phase 6: local companion runtime | **CLOSED (GitHub 10-13)** | S24 (`aa749ac`) | `--self-test` PASS on VPS; the real darwin/arm64 half still rides board #6 — note the early close. |
| 28 | Phase 6: opt-in hardware bridge | MAC VERIFY PENDING | S25 (`f42a8de`) + S49 pairing + S50 train handoff | Board #7; S49/S50 recipes in the November ledger. |
| 29 | Phase 6: data model split | MAC VERIFY PENDING | S26 (`5ae26cf`) | Board #8; device_artifacts ledger + `/api/bridge/artifacts`. |
| 30 | Phase 6: fluid end-to-end path, no terminal | OPEN — in progress | components: S23–S26, S49–S50 | The full fresh-install path is proven piecewise only; blocked on the board #5→#8 verify chain (order 5 clean-machine → 6→8). S71 (11-27) seeds the first-run demo dataset. |
| 31 | Generation UX: auto-fill use-case prompt | RESOLVED | S27 | Zero-LLM templates, owner-scoped, never writes; "Suggest" on Dataset detail. |
| 32 | Compare: parallelize four-way fan-out | RESOLVED | S28 | ThreadPoolExecutor fan-out with a thread-barrier test; stale ROADMAP checkbox fixed by S75. |
| 33 | Training error explainer | RESOLVED (rule map, not LLM) | S29 | 11 deterministic rules + generic fallback under failed runs (`GET /{id}/explain`); the ROADMAP LLM-summary upgrade stays backlog by choice. |
| 34 | Sharing: public/private datasets + models | RESOLVED | S31 + S32 + S53 | visibility columns, ShareToggle UI, `/library`, read-only public detail at `/library/datasets/:id` with the 404-no-leak invariant. |
| 35 | Advanced training mode (hyperparameters) | PARTIAL | S33 + S34 | LoRA rank/alpha + learning rate shipped with bounds + UI; batch/grad-accum/dropout/target-modules and the `advanced_config` JSON column stay ROADMAP backlog. |
| 36 | Training run visibility + history | RESOLVED | S35 + S36 | `/history` page, per-run dataset/base/iters/final-loss, loss replay, log viewer. |
| 37 | Brand pass: motif, Swagger theming, light/dark | PARTIAL | S39 | EmptyState family, icon sweep, light/dark verified; Swagger UI theming not started (ROADMAP brand). |
| 38 | In-app guides | OPEN — in progress | S30 (Train + Dataset detail) | S65 (11-19) adds Library/History/Settings hints, reusing the S30 pattern. |
| 39 | More model families beyond Llama 3.2 | RESOLVED | S37 + S38 | phi4-mini + gemma3:4b registry entries + 17 family/ladder tests. |
| 40 | Repo extraction: API Agents + API Infrastructure | PARTIAL — deferred by ADR | S40 (ADR-002) + S41 | Landed as in-repo `backend/api_agents/` with the 4 import-cut rules + boundary tests; separate showcase repos deferred per the ADR. |
| 41 | Platform expansion: RN, native macOS, Swift | DEFERRED | S42 + S43 spike notes | Boards #9–#10 for the spikes themselves; real builds gated on #25 sign-off per the November ledger. |
| 42 | Training: failures are silent | **CLOSED (signed off)** | H3 + `b99776d` + S29 + S36 | `except Exception as e` + error column (migration `3b7c1d9f4a2e`) + 425 MLX preflight + red error box; fuse.log tail appended (`b99776d`); explain cards (S29) and log viewer (S36). Carlos eyeballed the red box on run #1 and signed off. GitHub flip pending. |
| 43 | Compare: cap all columns at ~150 words | RESOLVED | H4 | Single `ANSWER_CAP` system prompt on all columns; the check rides board #4 ("every answer ≤ ~150 words" in DEMO Script A). |
| 44 | Docs/UX: 200–400 iters recommended | RESOLVED | H4 + QUICKSTART | `docs/QUICKSTART.md` iteration tiers (10-20 smoke / 200-400 recommended / 500+ deep); S71 wires the Welcome CTA into it. |
| 45 | Generation: pre-flight status + fast-fail dead providers | MAC VERIFY PENDING | `69b7d31` | `GET /api/generation/status` + ladder break on account-level errors + 60 s timeouts; VPS half live, the Mac check in the issue body still unrun (fold into board #4's E2E). |
| 46 | Training: fuse stage fails (exit 1) silently | OPEN — RCA pending | `b99776d` (no longer silent) | fuse.log tail now persisted on failed runs + `scripts/collect-run-logs.sh`; awaiting Carlos's paste-safe diagnostics block from the Mac. |

## Bookkeeping — GitHub flips owed

The lane commits via SSH and has **no issue-write token**, so upstream flips are
one-time manual steps for Carlos (or a future run with `gh auth`):

```bash
# the two signed-off browser-verify issues (this row's close-out):
gh issue close 1  --comment "H1 browser-verified, signed off — see S57/docs/GITHUB-ISSUES.md"
gh issue close 42 --comment "H3 browser-verified (red box on run #1), signed off — see S57/docs/GITHUB-ISSUES.md"
# the 23 train-resolved issues:
for i in 2 3 4 5 10 11 12 13 14 15 16 17 21 22 23 31 32 33 34 36 39 43 44; do
  gh issue close $i --comment "Shipped by the commit train — see docs/GITHUB-ISSUES.md (S57 reconciliation)"
done
```

## Summary (post-reconciliation, 2026-11-14)

- **Closed upstream:** #18, #20, #24, #27 → 4
- **Closed here (sign-off recorded, flip pending):** #1, #42 → 2
- **RESOLVED by the train, flip pending:** 23 issues (see Bookkeeping)
- **Shipped, Mac verify pending:** #6–#9, #26, #28, #29, #45 → 8 (board #1–#7; #6 has no board recipe yet)
- **Genuinely open threads:** #19 (umbrella, until S74) · #25 (ADR sign-off — the month's gating decision) · #30 (E2E path) · #35, #37, #40 (partials) · #38 (until S65) · #41 (deferred) · #46 (RCA) → 9

Sept's original "20 issues" estimate is superseded: #21–#41 were created as the
ROADMAP decomposition, #42–#46 as same-day demo-run reports.

**Priority order** (was: Sept 16–30 list) is now carried by
`docs/COMMIT-TRAIN-NOVEMBER.md`; the remaining threads above map to S63/S65/S66/S71/S73/S74.
