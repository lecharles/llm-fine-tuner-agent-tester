# GitHub Issues — Full List

All bugs, features, and infrastructure work identified during the Sept 15 demo run-through.

## Bugs (Priority: Fix before v0.1.0)

### #1 VPS team instance: login returns 401 despite valid credentials
**Severity:** Critical  
**Component:** Backend / Auth  
**Status:** Investigating  
**Description:**  
Signup succeeds (201), password verifies correctly in Python, but `/api/auth/login` returns 401 when called via the browser. Works via curl with form-encoded data. Suspect frontend is sending JSON instead of form-encoded, or a CORS/preflight issue.

**Steps to reproduce:**
1. Start VPS instance on port 8090
2. Navigate to `http://76.13.122.86:8090/login`
3. Enter credentials `team@teamox.dev` / `Gz8tNl13XvS70L6a`
4. Click Login → 401 Unauthorized

**Expected:** Login succeeds, JWT stored, redirect to dashboard  
**Actual:** 401 error, no redirect

**Root cause hypothesis:** Frontend `apiFetch` sends JSON body, but OAuth2PasswordRequestForm expects `application/x-www-form-urlencoded`.

**Fix:** Update frontend login handler to use URLSearchParams encoding.

---

### #2 Compare: failed columns show errors but don't persist to history
**Severity:** Medium  
**Component:** Backend / Chat  
**Status:** Fixed (commit 1d56f87)  
**Description:**  
When a column fails (out of credits, server died), the error is shown in the UI but not persisted. This is correct behavior — errors shouldn't pollute conversation history — but the UI should make it clearer that the column is "dead" for this session.

**Current behavior:** Red error bubble appears, next send retries the column.  
**Desired behavior:** After 2 consecutive failures, show a "column disabled" badge and stop retrying until the user clicks "Retry".

**Workaround:** None needed; current behavior is acceptable.

---

### #3 Generation: Ollama fallback doesn't auto-select a model
**Severity:** Low  
**Component:** Backend / Generation  
**Status:** Open  
**Description:**  
When both Anthropic and OpenAI are out of credits, generation falls through to Ollama. If multiple models are installed, it tries them in alphabetical order. Should prefer a configured default or the most recently used model.

**Current behavior:** Tries all installed models in `/api/tags` order.  
**Desired behavior:** Use `GENERATION_LOCAL_MODELS` env var if set, else pick the first model with "instruct" in the name, else alphabetical.

**Workaround:** Set `GENERATION_LOCAL_MODELS=llama3.1:8b` in `~/.llmtuner/.env`.

---

### #4 Training: loss curve not shown in real-time
**Severity:** Low  
**Component:** Frontend / Train  
**Status:** Open (planned for Sept 25)  
**Description:**  
Training runs show "running" status but no live loss curve. The train.log file is written, but the UI doesn't parse or display it.

**Current behavior:** Status badge updates, but no chart.  
**Desired behavior:** Poll `/api/training-runs/{id}/losses` every 5s, render a tiny line chart.

**Workaround:** Tail the log file manually: `tail -f ~/.llmtuner/_training_runs/{id}/train.log`.

---

### #5 Compare: hosted columns can't be swapped for local models
**Severity:** Medium  
**Component:** Frontend + Backend / Compare  
**Status:** Open (planned for Sept 27)  
**Description:**  
When both hosted columns (OpenAI, Anthropic) are out of credits, the user should be able to swap them for additional local models (e.g., Fine-tuned 2, Fine-tuned 3, or any Ollama model). Currently the column labels are hardcoded.

**Current behavior:** Four fixed columns: Fine-tuned, Vanilla, OpenAI, Anthropic.  
**Desired behavior:** Column picker dropdown per column; default to the four, but allow swapping to any installed Ollama model or any previously trained fine-tuned model.

**Workaround:** None; requires code change.

---

## Features (Priority: Ship by Sept 30)

### #6 Desktop app: `llmtuner app` opens floating browser window
**Severity:** High  
**Component:** CLI  
**Status:** Open (planned for Sept 16)  
**Description:**  
Add a `llmtuner app` command that opens the web UI in a floating browser-app window (Chrome `--app=`), sized to the welcome page. Falls back to the default browser if Chrome isn't found.

**Acceptance criteria:**
- `llmtuner app` opens Chrome with `--app=http://localhost:8000`
- Window is 1024×768, no address bar, no tabs
- If Chrome not found, opens default browser to the same URL
- `--size 800x600` flag overrides default dimensions

**Reference:** Ollama's "Apps" modal shows the pattern (see screenshot).

---

### #7 Desktop app: menu-bar integration (macOS)
**Severity:** High  
**Component:** CLI  
**Status:** Open (planned for Sept 21)  
**Description:**  
Add a `llmtuner menubar` command that creates a menu-bar extra (top-right status icon) with: status dot (green=running, red=stopped), "Open window", "Start server", "Stop server", "Quit". Uses `rumps` library.

**Acceptance criteria:**
- Llama icon appears in menu bar when `llmtuner menubar` runs
- Clicking icon shows dropdown with status + actions
- "Open window" launches the floating browser window (issue #6)
- "Quit" stops the server and exits the menu-bar app

**Reference:** Ollama's menu-bar extra (see screenshot).

---

### #8 Desktop app: icon pipeline (favicon.svg → AppIcon.icns)
**Severity:** Medium  
**Component:** Scripts  
**Status:** Open (planned for Sept 19)  
**Description:**  
Create a script `scripts/make_app_icon.sh` that converts `frontend/public/favicon.svg` to `AppIcon.icns` using `sips` and `iconutil`. The icon is used for the `.app` bundle (issue #9) and the menu-bar extra (issue #7).

**Acceptance criteria:**
- Script reads `frontend/public/favicon.svg`
- Generates 1024×1024 PNG, then 16/32/64/128/256/512/1024 sizes
- Packages into `AppIcon.icns`
- Script is idempotent (overwrites existing icon)

**Workaround:** Use the SVG directly (browsers handle it fine).

---

### #9 Desktop app: `.app` bundle for native macOS identity
**Severity:** Medium  
**Component:** CLI + Scripts  
**Status:** Open (planned for Sept 20)  
**Description:**  
Add a `llmtuner bundle` command that generates `LLM Tuner.app` with:
- `Info.plist` (bundle ID, version, icon)
- Launcher script (starts the server, opens the window)
- `AppIcon.icns` (from issue #8)

**Acceptance criteria:**
- `llmtuner bundle` creates `~/Applications/LLM Tuner.app`
- Double-clicking the app starts the server and opens the window
- App name appears in the top-left menu bar as "LLM Tuner"
- Dock icon is the llama logo

**Workaround:** Use `llmtuner up` + browser manually.

---

### #10 Welcome/motivation page
**Severity:** Medium  
**Component:** Frontend  
**Status:** Open (planned for Sept 18)  
**Description:**  
Add a `/welcome` route (and sidebar entry) that explains the project's motivation: one-click local fine-tuning, team collaboration, privacy-first. This is the landing page for the desktop app (issue #6).

**Acceptance criteria:**
- `/welcome` route renders a static page with:
  - Project name + tagline
  - 3-sentence pitch (local, team, privacy)
  - Screenshot of the compare view
  - "Get started" button → `/datasets`
- Sidebar has a "Welcome" entry (first item, above "Get started")

**Workaround:** None; content is static.

---

### #11 Team lanes: service-token auth for agent lanes
**Severity:** High  
**Component:** Backend  
**Status:** Open (planned for Sept 22)  
**Description:**  
Add a `API_SERVICE_TOKENS` env var (comma-separated list) that grants read/write access to the VPS instance without a user session. Each token is tied to a lane name (e.g., `teamox-hermes`, `teamox-openclaw`).

**Acceptance criteria:**
- `API_SERVICE_TOKENS=hermes:abc123,openclaw:def456` in `env`
- Requests with `Authorization: Bearer abc123` are treated as the "hermes" lane
- Lane can create datasets, queue generation, list models
- Lane cannot delete datasets or modify other lanes' data
- `GET /api/status` returns lane name + permissions

**Workaround:** Use the team user credentials manually.

---

### #12 Pytest suite
**Severity:** Medium  
**Component:** Tests  
**Status:** Open (planned for Sept 23)  
**Description:**  
Add a pytest suite covering:
- Auth/me regression (local mode, JWT mode)
- Env precedence (backend/.env vs ~/.llmtuner/.env)
- Generation ladder (Anthropic → OpenAI → Ollama fakes)
- Local server lifecycle (start, reuse, restart, reap)
- Splash render (no UI build → status page)

**Acceptance criteria:**
- `pytest` runs in <10s
- All tests pass on macOS + Linux
- Coverage >80% for `backend/generation/`, `backend/chat/`, `backend/routers/auth.py`

**Workaround:** Manual testing (current state).

---

### #13 CI: GitHub Actions
**Severity:** Low  
**Component:** Infrastructure  
**Status:** Open (planned for Sept 24)  
**Description:**  
Add `.github/workflows/ci.yml` that runs on every push:
- Python compile check (all `.py` files)
- Pytest suite (issue #12)
- Frontend build (`npm run build`)
- README badge

**Acceptance criteria:**
- CI runs on push to `main`
- All checks pass
- README shows "CI: passing" badge

**Workaround:** Manual checks before push.

---

### #14 Dataset import: CSV/JSONL upload
**Severity:** Low  
**Component:** Backend + Frontend  
**Status:** Open (planned for Sept 26)  
**Description:**  
Add a "Import dataset" button on the Datasets page that accepts CSV or JSONL files. Each row becomes a Q&A pair.

**Acceptance criteria:**
- Upload button on `/datasets` page
- Accepts `.csv` (columns: `question`, `answer`) or `.jsonl` (one JSON object per line)
- Creates a new dataset with the uploaded pairs
- Shows row count after import

**Workaround:** Use the "Import preset" dropdown (limited to built-in presets).

---

### #15 Compare: hosted-column model pickers
**Severity:** Low  
**Component:** Frontend + Backend  
**Status:** Open (planned for Sept 27)  
**Description:**  
Allow the user to pick which hosted model each column uses (e.g., swap OpenAI `gpt-4o-mini` for `gpt-5.5`, or Anthropic `claude-opus-4-8` for `claude-sonnet-5`). Also allow swapping to any installed Ollama model.

**Acceptance criteria:**
- Each column has a dropdown (default: current model)
- Dropdown lists: all installed Ollama models, all previously trained fine-tuned models, hardcoded hosted models
- Selection persists for the session
- Column label updates to reflect the chosen model

**Workaround:** Edit `schemas/chat.py` defaults (requires restart).

---

### #16 Docs: README rewrite + screenshots
**Severity:** Low  
**Component:** Documentation  
**Status:** Open (planned for Sept 28)  
**Description:**  
Rewrite the README to reflect the current state:
- One-paragraph pitch
- Installation (Mac + VPS)
- Quickstart (generate → train → compare)
- Screenshots (compare view, train page, VPS instance)
- Roadmap link

**Acceptance criteria:**
- README is <500 lines
- All links work
- Screenshots are in `docs/screenshots/`

**Workaround:** Current README is functional but verbose.

---

### #17 Shared-instance hardening
**Severity:** Medium  
**Component:** Backend  
**Status:** Open (planned for Sept 29)  
**Description:**  
Harden the VPS instance for shared use:
- Rate limit signup (1 per IP per hour)
- Refuse `LOCAL_MODE=true` when binding to non-loopback
- Credential rotation doc (how to change JWT secret, reset passwords)

**Acceptance criteria:**
- Signup returns 429 after 1 attempt per IP per hour
- `LOCAL_MODE=true` + `--host 0.0.0.0` → startup error
- `docs/CREDENTIALS.md` explains rotation steps

**Workaround:** Trust the team not to abuse it (current state).

---

### #18 v0.1.0 release
**Severity:** High  
**Component:** Release  
**Status:** Open (planned for Sept 30)  
**Description:**  
Tag v0.1.0, write release notes, run final E2E demo.

**Acceptance criteria:**
- Git tag `v0.1.0` on `main`
- Release notes in `docs/RELEASE-v0.1.0.md`
- Demo script `docs/DEMO.md` runs end-to-end on Mac + VPS
- All issues #1–#17 closed or deferred

**Workaround:** None; this is the goal.

---

## Infrastructure (Ongoing)

### #19 Commit train automation
**Severity:** Medium  
**Component:** Automation  
**Status:** Open (planned for Sept 16)  
**Description:**  
Automate the daily commit train (one slice per day, Sept 16–30). Use a cron job or Hermes lane to:
- Check if today's slice is due
- Implement the slice (or verify it's already done)
- Commit with today's date
- Push to `main`

**Acceptance criteria:**
- One commit per day, Sept 16–30
- Each commit message references the slice (e.g., "feat: S2 — desktop app")
- Push happens at 12:00 UTC
- `PAUSE` file stops the train

**Workaround:** Manual commits (current state).

---

### #20 VPS keepalive cron
**Severity:** Low  
**Component:** Infrastructure  
**Status:** Done (commit 19ee13d)  
**Description:**  
Cron job checks `/health` every 5 minutes, restarts the server if down.

**Status:** Installed on VPS, running.

---

## Summary

- **Bugs:** 5 (1 critical, 1 fixed, 3 low/medium)
- **Features:** 13 (3 high, 6 medium, 4 low)
- **Infrastructure:** 2 (1 done, 1 ongoing)
- **Total:** 20 issues

**Priority order for Sept 16–30:**
1. #1 (VPS login) — critical, blocks team use
2. #6 (desktop app) — high, flagship feature
3. #11 (team lanes) — high, blocks Teamox integration
4. #18 (v0.1.0 release) — high, the goal
5. #7, #8, #9 (desktop app parts 2–4) — high, complete the desktop experience
6. #10 (welcome page) — medium, needed for desktop app landing
7. #5, #15 (compare column swaps) — medium, improves UX
8. #12, #13 (tests + CI) — medium, quality gate
9. #2, #3, #4, #14, #16, #17 (polish) — low/medium, nice-to-have
