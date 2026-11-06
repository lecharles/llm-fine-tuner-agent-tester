# MAC-VERIFY — the 10 pending Mac verification slices

S45 retro logged "10-slice Mac verify debt": every slice below is marked
**DONE (Mac verify pending)** in the ledger — code shipped and VPS-verified,
but the Apple-Silicon half has never been run. This doc turns each pending
recipe into an exact checklist. Tick the date column (or reply with the step
that diverged) and the lane flips the slice to plain DONE.

Recipe sources are the original commit bodies — commands reproduced verbatim
where possible; `git log --grep <slice>` for full context.

## Verification board

| # | Slice | What it proves | Source commit | Verified (date) |
|---|-------|----------------|---------------|-----------------|
| 1 | S5 — icon pipeline | `make_app_icon.sh` renders llama icon → `.icns` on macOS | `e0070ea` | ☐ |
| 2 | S6 — app bundle | `LLM Tuner.app` double-click: Dock identity + floating window | `2eb9b32` | ☐ |
| 3 | S7 — menu-bar extra | `llmtuner menubar` (rumps) status dot + controls | `2eb9b32` (S5/S6/S7 chain) | ☐ |
| 4 | S16 — v0.1.0 E2E | tag checkout → doctor → `up` → DEMO Script A end-to-end | `0d2a2a5` | ☐ |
| 5 | S23 — macOS installer | curl \| bash runtime install + `.command` double-click + idempotency | `01d66cf` | ☐ |
| 6 | S24 — companion | `companion.py --self-test` PASS on real darwin/arm64 + live pairing | `aa749ac` | ☐ |
| 7 | S25 — opt-in bridge | consent prompt → scoped grant → bridge online → real-data job ok:true | `f42a8de` | ☐ |
| 8 | S26 — data split | device artifact pointer ledger: artifacts stay local, hosted shows metadata | `5ae26cf` | ☐ |
| 9 | S42 — React Native spike | Expo WebView shell loads :8090 with ATS exception | `c81bf5b` | ☐ |
| 10 | S43 — Swift spike | swiftc menu-bar snippet + Process self-test + Keychain CLI check | `fb7579e` | ☐ |

Also carry over from S45 (`2697a48`): `git tag --list 'v0.1*'` shows v0.1.0 +
v0.1.1, and `v0.1.1` resolves to the month-close commit. Fold into #4 below.

---

## 1. S5 — icon pipeline (`e0070ea`)

```bash
cd ~/llm-fine-tuner-agent-tester && git pull --ff-only
./scripts/make_app_icon.sh
```
Expect: `ok: <repo>/build/AppIcon.icns (NNNNN bytes, from .../favicon.svg)`
```bash
ls build/appicon.iconset
sips -g pixelWidth -g pixelHeight build/appicon.iconset/icon_512x512@2x.png
```
Expect: 10 PNGs (16/32/128/256/512 + @2x); @2x measures 1024×1024, llama glyph
on dark rounded square. Open `build/AppIcon.icns` in Preview — crisp at 16px
and 1024px zoom. Re-run the script once more: identical `ok:` line (idempotent).

## 2. S6 — LLM Tuner.app bundle (`2eb9b32`)

Do #1 first, then:
```bash
PYTHONPATH=cli python3 -m llmtuner bundle
```
Expect: `📦 Built LLM Tuner.app at ~/Applications/LLM Tuner.app` with
`icon: .../Resources/AppIcon.icns`.
```bash
open ~/Applications/"LLM Tuner.app"
```
Expect: Terminal starts the local backend on :8000; within ~20s a floating
tabless LLM Tuner window appears. Dock + app menu say "LLM Tuner" with the
llama icon (note here if Chrome's menu name leaks instead). Re-open while the
backend already runs → **no** second Terminal. Re-run the bundle command →
clean overwrite, no errors.

## 3. S7 — menu-bar extra (`llmtuner menubar`, rumps)

```bash
PYTHONPATH=cli python3 -m llmtuner menubar
```
Expect: llama status dot in the menu bar; menu offers open window, start/stop,
quit; dot flips with backend state. Quit via the menu — no orphaned process
(`pgrep -f menubar` empty after). If rumps is missing, install with
`python -m pip install rumps` (it is the documented optional dep).

## 4. S16 — v0.1.0 E2E (`0d2a2a5`)

```bash
git pull --ff-only && git fetch --tags
git tag --list 'v0.1*'                  # Expect: v0.1.0 and v0.1.1
git checkout v0.1.0 && git describe --tags   # Expect: v0.1.0
PYTHONPATH=cli python3 -m llmtuner --version # Expect: "llmtuner 0.1.0"
PYTHONPATH=cli python3 -m llmtuner doctor    # Expect: Apple Silicon + mlx-lm ok
PYTHONPATH=cli python3 -m llmtuner up --port 8000
```
Open `http://localhost:8000/docs` → header "LLM Fine Tuner & Agent Tester
API — version 0.1.0"; `/openapi.json` shows `"version": "0.1.0"`. Then run
`docs/DEMO.md` **Script A** end-to-end (~20 min): /welcome → signup →
generate 10 pairs (Ollama badges) → import demo-refunds.csv → train 10–20
iters (live loss curve; a dead run shows the red error box) → compare 5
columns; tuned answer cites 30-day+receipt; every answer ≤ ~150 words.
`git checkout main` when done.

## 5. S23 — macOS installer (`01d66cf`)

```bash
bash -n install/macos.sh && bash -n install/macos-installer.command  # prints nothing
curl -fsSL https://raw.githubusercontent.com/lecharles/llm-fine-tuner-agent-tester/main/install/macos.sh | bash
```
Expect: green ✅ per stage, ending "Local runtime installed at ~/.llmtuner" +
doctor output. In a **new** Terminal tab: `llmtuner doctor` then `llmtuner up`
→ http://localhost:8000 serves the web shell. One-file path: Finder →
right-click `install/macos-installer.command` → Open → Open (Gatekeeper blocks
plain double-click first run). Idempotency: re-run the curl pipeline →
"Updating existing install", no errors. Skip flag:
`LLMTUNER_SKIP_OLLAMA=1 bash install/macos.sh` → notice it skipped Ollama.
Optional: 20-iter run on the demo dataset, queued → running → completed.
Findings on #26; flips to DONE after pass.

## 6. S24 — local companion self-test (`aa749ac`)

```bash
cd ~/.llmtuner && git pull origin main && source .venv/bin/activate
python -m pip install -r companion/requirements.txt   # "Successfully installed websockets-1x"
python companion/companion.py --self-test
```
Expect: `[companion] paired as companion test-c1 on darwin/arm64 mlx=True
ollama=True` then `SELF-TEST PASS — ...`; `echo $?` → 0. If mlx/ollama flags
are False, run `llmtuner doctor` and fix first. Live half (pairing against a
running backend, job frames) completes when S49/S50 tokens land — record
self-test state here regardless.

## 7. S25 — opt-in bridge (`f42a8de`)

On the Mac, repo: `git pull origin main`. In the hosted web app (:8090), open
the Bridge consent sheet → name the device (e.g. `studio-mac`), keep default
scopes → **Copy** the token, paste and run the shown companion command in the
Mac terminal. Expect: within ~2s the Bridge row turns online/green with the
Mac capability snapshot; submit a small job (status or train probe) → payload
with real Mac data, `ok:true`. Then revoke in the UI and confirm the WS drops
(terminal exits with auth error = terminal, exit code 2). Full steps in
`git show f42a8de` body; divergence → #28.

## 8. S26 — device/hosted data split (`5ae26cf`)

Prereq: #7 passed (grant exists). With the team instance env, create/update a
Bridge grant, let the companion sync, then on the hosted side:
`GET /api/bridge/artifacts` → Expect: one row per device artifact (kind
adapter, `device_name: studio-mac`) — metadata only, no weights uploaded;
`DELETE` removes the pointer, file stays on the Mac. Spot-check the local
half: `llmtuner` train/export/serve still find adapter + fused dirs on the
Mac exactly as before. Full probe script in `git show 5ae26cf` body;
findings → #29.

## 9. S42 — React Native shell spike (`c81bf5b`)

Per `docs/SPIKE-REACT-NATIVE.md` (recommendation A: Expo WebView,
private-TestFlight first):
```bash
npx create-expo-app@latest lt-shell && cd lt-shell && npx expo install react-native-webview
```
Replace `App.js` with the shell from the commit body (`SHELL_URL =
http://76.13.122.86:8090`), add the ATS `NSAllowsArbitraryLoads` exception per
the doc, then `npx expo start` on a real iPhone (dev build).
Expect: :8090 login screen renders in the WebView; sign in; loss curve polls.
Record the three gating conditions from the spike (TLS, ATS waiver, session
storage) as pass/fail. Findings on #25.

## 10. S43 — Swift menu-bar spike (`fb7579e`)

Per `docs/SPIKE-NATIVE-MACOS.md` §Verification, three numbered checks:
```bash
# 1. compile the menu-bar snippet from the doc
swiftc /tmp/lt-menubar.swift -o /tmp/lt-menubar && /tmp/lt-menubar   # Expect: status item appears
# 2. Process self-test: spawn the Python companion from Swift and read exit code
#    (snippet in doc §Verification) — Expect: exit 0, hello/welcome frame logged
# 3. Keychain CLI check for pairing-token storage:
security add-generic-password -s llmtuner-pair -a carlos -w testtoken && \
  security find-generic-password -s llmtuner-pair -g; security delete-generic-password -s llmtuner-pair
```
Expect: item 2 proves option A (thin Swift shell over the S24 companion) is
viable before any Gatekeeper/Developer-ID decision. Findings on #25.

---

Order to run them: 1 → 2 → 3 is one sitting on the repo checkout; 4 is the big
E2E; 5 is best on a clean machine or disposable user; 6–8 build on each other
(installed runtime → companion → bridge → artifacts); 9–10 are spike-only and
don't block the v0.2 core.
