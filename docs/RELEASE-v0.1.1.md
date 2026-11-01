# LLM Tuner v0.1.1 — Release Notes

**Tag:** `v0.1.1` on `main` · **Date:** 2026-11-01 (slice S45, planned 10-31) · **Closes:** the October month-close. v0.1.0 (see `docs/RELEASE-v0.1.0.md`) → v0.1.1 covers S17–S45 plus the hotfix inserts H3/H4.

The v0.1.1 goal: make the shipped loop *pleasant and safe* — a full design/a11y pass, shared-library sharing, hyperparameter + history UX, the web shell publicly deployed, Phase 6 decided (hybrid), and perf/security swept — without breaking a single API contract.

## What shipped since v0.1.0

| Area | Slices | Highlights |
|------|--------|-----------|
| Look & feel | S17–S19, S39 | theme.css foundation + status badges + iters stepper/chips, ConfirmDialog + VuMeter loader, WCAG AA contrast + keyboard/focus/skip-link a11y, shared EmptyState + icon sweep + fresh login/signup screenshots |
| Account UX | S20 | `GET /api/auth/me`-fed Linear-style user menu in the sidebar |
| Public instance | S21, S44 | web shell live on the VPS :8090 (`docs/PUBLIC-INSTANCE.md` runbook), then the perf/security sweep: 9 list-query indexes, CSP + baseline security headers, login failed-attempt throttle, OSV dependency audit (`backend/DEPENDENCY-AUDIT.md`) |
| Phase 6 direction | S22, S42, S43 | ADR-001 recommends hybrid (web shell + local companion) — Carlos sign-off on #25 pending; React Native + native-macOS spike docs with numbered Mac recipes |
| Local runtime path | S23–S26 | `install/macos.sh` + double-click installer, WS companion skeleton (`llmtuner-companion/0`), opt-in bridge consent + scoped/revocable permissions, device-artifact pointer ledger — **all Mac verify pending** |
| Datasets & training | S27, S33, S34, S29, S30 | zero-LLM use-case prompt suggester, LoRA rank/alpha/lr with validated UI, training-error explainer cards, in-app hint bubbles |
| Sharing | S31, S32 | private/public visibility on datasets + models (owner-or-public reads, no existence leak) and the `/library` public page with share toggles |
| History & compare | S35, S36, S28 | run-history endpoint + `/history` page with loss replay + log viewer; four-way compare fan-out parallelized |
| Generation breadth | S37, S38 | phi-4-mini + gemma-3 recipe registry, fallback ladder walks installed models in registry order; 17 registry/ladder tests |
| Architecture | S40, S41 | ADR-002 + extraction of the provider-client layer into `backend/api_agents/` with a CI-boundary guard |

## Quality gates at tag time (2026-11-01)

- `python3 -m py_compile` on every touched backend file (`.venv-smoke` 3.12.3)
- fresh `import main` smoke from `backend/`
- pytest **121 green** (was 46 at v0.1.0) — `backend/.venv-smoke/bin/python -m pytest tests -q`
- `tsc -b && vite build` green; `frontend/dist/index.html` verified CSP-compatible (one same-origin module script, no inline scripts)
- alembic single linear head `f2c9d8e4a715`, applied on the live `:8090` DB

## Version surfaces

- `llmtuner --version` → `llmtuner 0.1.1` (source of truth: `cli/llmtuner/__init__.__version__`; `__main__` fallback bumped in lockstep)
- FastAPI/openapi `/docs` header: `0.1.1` (`backend/main.py`)
- `frontend/package.json`: `0.1.1`
- Git tag: `v0.1.1`

## Breaking changes

None for existing API consumers. New behaviors worth knowing:

- `POST /api/auth/login` can return **429 + Retry-After** after ≥10 *failed* attempts per (IP, email) in a rolling minute (`LOGIN_FAILED_LIMIT_PER_MINUTE`, 0 disables). Successes are never throttled and clear the window.
- Every HTTP response from the API process now carries CSP + `X-Content-Type-Options` / `Referrer-Policy` / `X-Frame-Options`; `/docs` + `/redoc` are CSP-exempt.

## Known issues / deferred to November

- Live `:8090` still runs the pre-S41/S44 process until its next restart — headers/indexed queries/`api_agents` go live then (restart recipe in the November draft).
- 10 MAC slices shipped but awaiting Carlos's Mac verification (S2, S5–S7, S16, S23–S26, S42, S43) — recipes live in their commit bodies.
- 6 legacy screenshots still pending a Mac capture session; `deploy/` is root-owned on the VPS (one-time `sudo chown -R hermes:hermes deploy/` unblocks the OLLAMA.md re-point).
- H1/H3 UI checks still `AWAIT BROWSER VERIFY`.

Full slice-by-slice detail: `docs/COMMIT-TRAIN.md`. October retro: `docs/RETRO-2026-10.md`. November plan: `docs/COMMIT-TRAIN-NOVEMBER.md`.
