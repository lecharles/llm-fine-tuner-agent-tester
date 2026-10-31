# Spike S43 — native macOS (Swift) companion: notes + feasibility matrix

- **Date:** 2026-10-31 (implements the 10-29 row, two days overdue)
- **Status:** Desk-research spike. The lane has NOT compiled or run any Swift
  on a Mac — nothing below is verified. §Verification is the Mac recipe that
  tests the load-bearing claims; STATUS stays "DONE (Mac verify pending)"
  until Carlos runs it. Do not treat any estimate here as fact.
- **Related:** docs/ADR-001-phase6-hybrid-vs-local-first.md (hybrid shape),
  docs/SPIKE-REACT-NATIVE.md (S42, the mobile sibling of this spike),
  S23 (install/macos.sh runtime), S24–S26 (Python companion + bridge),
  S6/S7 (`llmtuner bundle` + `llmtuner menubar`, rumps-based), issue #25.

## The question

Phase 6 says the Mac does the heavy MLX work via the companion, which dials
out to the web hub. Today that companion is **Python** (`companion/companion.py`,
S24) and its desktop presence options are also Python (rumps menubar S7,
generated .app bundle S6). Does a **native Swift macOS app** buy us anything
worth the cost — and if so, how much of the companion should go native?

## Grounding facts from this repo as of S42

- The Python companion is a **transport + orchestration shell, not the
  trainer**: an asyncio WebSocket client speaking JSON frames, protocol id
  `llmtuner-companion/0` (hello/welcome/job/event/result — the pairing token
  rides inside the hello frame, never in a URL). Job kinds:
  `status|train|fuse|export|serve`. The real work goes to the loopback
  LOCAL_MODE backend (auto-started uvicorn) and to `mlx_lm.fuse` /
  `ollama pull`. `--self-test` (in-process fake hub + fake API) runs
  anywhere Python does — it already passed on the VPS in S24.
- Training itself is Python-only: the pipeline is `mlx_lm.lora` with the S33
  hyperparameters. There is no drop-in Swift equivalent of that trainer today;
  mlx-swift exists but the LLM fine-tune loop we depend on does not.
- Distribution reality: S23 installs the runtime via `curl | bash` into the
  user's home; S6 generates `LLM Tuner.app` with an Info.plist + launcher.
  An unsigned, script-assembled bundle is fine for Carlos; it is not a story
  we can hand to a third party (Gatekeeper).
- Token storage today: `~/.llmtuner/.env` / env vars. No Keychain anywhere.
- The web shell (the source of requests) is unchanged in every option —
  per ADR-001 the phone/browser never talks to the Mac; hub does.

## Options considered

**A. Thin Swift shell around the Python companion.** A small AppKit/SwiftUI
menu-bar app that (1) finds the S23 runtime (`~/.llmtuner/…`), (2) starts/
stops `companion.py` as a `Process` (or LaunchAgent) with the pairing token
pulled from **Keychain** instead of `.env`, (3) shows state (dial-out up/
down, current job stage parsed from the companion's existing console log
lines), (4) registers a `llmtuner://` deep-link to receive the pairing
token from the web shell's bridge-consent page (S25 UI). Python keeps the
protocol and all MLX work — one implementation, zero drift. Rough effort:
2–4 days for a personal demo; +1 week for a notarized, auto-updating build.

**B. Full Swift companion rewrite.** Re-implement dial-out in Swift
(`URLSessionWebSocketTask` is genuinely enough for the WS side) **and** the
local pipeline: launch uvicorn from Swift `Process`, port `mlx_lm.fuse`
calls, reimplement train-log parsing. The training call-out cannot escape
Python anyway (`mlx_lm` is the trainer), so B ends up as "A plus a Swift
re-implementation of ~500 lines of proven orchestration that then has to
track every future protocol/job-kind change twice." Rough effort: weeks.
**Rejected** — dual-implementation drift is the exact risk ADR-001 named.

**C. Status quo: rumps menubar (S7) + generated bundle (S6).** Zero new
work; already DONE-pending-Mac-verify. Honest shortcomings: rumps is
minimally maintained, no Keychain, no code-signing/notarization path,
no login-item management, and the .app identity story is a script's best
effort. Fine for Carlos's own machine, weak for "download LLM Tuner for
macOS."

## Feasibility matrix

| Dimension | A: Swift shell | B: Swift rewrite | C: Python as-is |
|---|---|---|---|
| Effort to first demo | 2–4 days | weeks | already built (pending Mac verify) |
| Protocol implemented once | ✅ (Python owns it) | ❌ two implementations | ✅ |
| Native menu-bar identity (icon, no Terminal window, Dock-free) | ✅ | ✅ | ⚠️ rumps is close but not native |
| Keychain for pairing/JWT | ✅ first-class | ✅ | ❌ env-file today |
| Login item / background launch | ✅ SMAppService / LaunchAgent | same | ⚠️ manual |
| Code-sign + notarize for outside distribution | ✅ needs Apple Developer ID | same, but bigger attack surface to sign | ❌ script-generated bundle |
| Deep-link pairing handoff (`llmtuner://`) | ✅ | ✅ | ❌ (no bundle-level URL registration) |
| TCC/permission prompts (Files, Ollama port) | native prompts | native prompts | ⚠️ inherited via Terminal/venv |
| Update story (Sparkle/AsyncAlts) | ✅ mature in Swift | ✅ | ❌ DIY |
| CI cost | macOS runners only for release builds | macOS runners for every protocol change | zero new CI |
| Risk to ADR-001 hybrid shape | none — companion stays the same daemon | drift risk on `llmtuner-companion/0` | none |
| What breaks first | runtime discovery if S23 layout changes — pin a stable path | protocol changes land in Python first, Swift lags | rumps upstream rot |

## Findings / open questions

1. **The trainer anchors everything to Python.** Any option that keeps
   `mlx_lm.lora` as the engine gets most of Swift's value from a *shell*,
   not a rewrite. B is only interesting if MLX Swift ships a real LoRA
   trainer — worth a quarterly check, not a build-out now.
2. **Distribution is the actual driver.** For personal use C already
   works. If "hand a .dmg to someone else" becomes a goal, A's Keychain +
   signing + login-item + update story is the right cost. This is a
   product question for #25, not a technical one.
3. **Pairing token handling needs the S25 flow to be real.** A's deep-link
   handoff assumes the web shell can mint a short-lived pairing token on a
   consent page (the S25 bridge UI). Until the hub accepts dial-out for
   non-self-test runs, A's menu bar can only supervise `--self-test`.
4. **Runtime path contract:** the Swift shell must not hardcode venv
   internals — pin the contract to "S23 installs a discoverable runtime
   under `~/.llmtuner/` and companion.py is launched with its python."
   If S23's layout changes, A breaks first; record the path contract in
   install/README.md if A is approved.
5. **Keep C shipping regardless.** S6/S7 Mac verification is still pending
   (see COMMIT-TRAIN); A would *wrap* the same daemon C launches, so C's
   verification steps all carry forward.

## Recommendation (lane's pick, Carlos signs off on #25)

Do **A**, but only when the distribution goal is real: a ~400-line AppKit
menu-bar shell that supervises the existing Python companion, reads the
pairing token from Keychain, and registers `llmtuner://pair` for the S25
consent handoff. Python remains the single implementation of
`llmtuner-companion/0`. Reject B now; keep C as the fallback for personal
use and verify it on the Mac in any case. Preconditions before building:
(1) S25 hub dial-out works end-to-end, (2) pairing tokens minted by the
web shell, (3) S23 runtime layout frozen as a documented contract, (4) an
Apple Developer ID decision for signing/notarization.

## Verification (Mac recipe — the lane cannot run any of this)

This spike's load-bearing claims are: Swift toolchain compiles a menu-bar
shell, `Process` can launch the Python companion's `--self-test` from a
native app, and Keychain read/write works. Prove those with the numbered
steps; report each step's actual output on #25. Nothing below is claimed
to work — the snippet is demo-grade, unrun by the lane.

1. `xcode-select -p` → expect `/Applications/Xcode.app/Contents/Developer`
   (Xcode 15+). `swift --version` → expect a Swift 5.9+ line. If these fail,
   everything after is blocked; say so on #25 and stop.
2. `mkdir -p ~/spikes/ns-companion && cd ~/spikes/ns-companion` and save the
   §snippet below as `menubar-shell.swift` (it is also copied verbatim in
   the S43 commit body).
3. `cd ~/src/llm-fine-tuner-agent-tester && git pull origin main` (adjust
   to wherever your Mac clone lives) → expect the repo current, including
   `companion/companion.py` from S24.
4. Compile: `swiftc -O ~/spikes/ns-companion/menubar-shell.swift -o ~/spikes/ns-companion/llmtuner-shell`
   → expect a silent success and a binary at that path. Compile errors = a
   finding for #25; paste them.
5. Run: `~/spikes/ns-companion/llmtuner-shell` (edit `REPO` at the top of
   the snippet to your clone path first) → expect a **●** status item to
   appear in the macOS menu bar. No Dock icon should appear (snippet sets
   `.accessory` policy).
6. Click the item → "Run companion self-test" → expect a second menu line
   to change from `last run: (none)` to `last run: PASS` or `FAIL` within
   ~15s (the snippet tails companion.py's own exit code). PASS here validates
   claims 1–2 of this spike on your Mac; FAIL means capture Terminal output
   from step 7 before concluding.
7. Sanity-run the same self-test outside Swift:
   `python3 -m venv /tmp/s43-venv && /tmp/s43-venv/bin/pip install websockets && /tmp/s43-venv/bin/python <repo>/companion/companion.py --self-test`
   → expect `self-test PASS` (this mirrors the S24 VPS result; if it fails
   on the Mac, the Python side — not Swift — is the blocker).
8. Keychain claim: `security add-generic-password -a "$USER" -s llmtuner-pair-demo -w 'hunter2-not-a-real-token'`
   then `security find-generic-password -s llmtuner-pair-demo -w` → expect
   the CLI to store and echo the secret. This is the storage path option A
   proposes for the pairing token (the snippet itself keeps the demo token
   inline; a real build would use the SecItem API).
9. Cleanup: `security delete-generic-password -s llmtuner-pair-demo`, quit
   the shell via its menu.
10. Post findings to issue #25: which steps passed/failed, `swift --version`
    output, and whether you would actually want menu-bar supervision (A)
    over the rumps menubar (C) on your daily machine — that preference is
    the decision input.

### Snippet (menubar-shell.swift, demo-grade, never compiled by the lane)

```swift
import AppKit

let REPO = "/Users/YOU/src/llm-fine-tuner-agent-tester" // edit me

final class Shell {
    let status = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
    var lastRun = "(none)"

    func makeMenu() -> NSMenu {
        let m = NSMenu()
        m.addItem(withTitle: "Run companion self-test",
                  action: #selector(runSelfTest), keyEquivalent: "").target = self
        m.addItem(withTitle: "last run: \(lastRun)", action: nil, keyEquivalent: "")
        m.addItem(withTitle: "Quit", action: #selector(NSApplication.terminate(_:)),
                  keyEquivalent: "q")
        return m
    }

    @objc func runSelfTest() {
        let p = Process()
        p.executableURL = URL(fileURLWithPath: "/usr/bin/python3")
        p.arguments = ["\(REPO)/companion/companion.py", "--self-test"]
        p.standardOutput = Pipe(); p.standardError = Pipe()
        try? p.run()
        p.waitUntilExit()
        lastRun = (p.terminationStatus == 0) ? "PASS" : "FAIL(\(p.terminationStatus))"
        status.menu = makeMenu()   // rebuild so the label updates
    }

    func start() {
        status.button?.title = "●"
        status.menu = makeMenu()
    }
}

let app = NSApplication.shared
app.setActivationPolicy(.accessory)   // menu-bar only: no Dock icon
let shell = Shell(); shell.start()
app.run()
```

The snippet deliberately has no Info.plist: as a bare binary it is *not* a
real .app — proof of the toolchain and the Process bridge only. A shipping A
needs the S6-style bundle plus signing; see §preconditions.
