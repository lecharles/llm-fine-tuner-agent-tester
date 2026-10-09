# ADR-001 — Phase 6 architecture: hybrid web shell + local companion vs full local-first

- **Date:** 2026-10-09
- **Status:** Proposed (lane recommendation; pending Carlos's sign-off on issue #25)
- **Deciders:** Carlos (final call), commit-train lane (drafting)
- **Related:** issue #25, docs/ROADMAP.md "Phase 6", S21/`docs/PUBLIC-INSTANCE.md`
  (deployed web shell), scheduled S23 (installer), S24 (companion), S25 (bridge),
  S26 (data split)

## Context

Phase 6 closes the product gap: today the experience is disjointed — part of the
app lives on the VPS, training/models live on the user's Mac, and nothing ties
them together. North star (ROADMAP): *as easy to use as any web app, but the
compute and the user's data live on the user's own machine.* A fresh install
must reach sign-in → dataset → train → export → compare **without a terminal**.

Constraints that bound the decision:

1. **MLX training is Apple Silicon only.** The VPS can never run training, fuse,
   or export locally-computed models. Any fully-serverless option is dead on
   arrival.
2. We already ship both halves separately: `llmtuner up` (local FastAPI + Vite
   shell in a browser-app window, S2/S6) and the VPS team instance (S21, #24).
3. The S8 lane-token model and S15 shared-instance hardening exist; the hosted
   side is multi-user with accounts and rate limits.
4. Solo-maintainer reality: every kept architecture must be buildable by the
   daily lane + one Mac owner.

## Options

### Option A — Hybrid: online web shell + local companion (recommended)

The hosted site (URL, account, shareable datasets/models metadata, generation
ladder with cloud fallback) stays on the VPS. A **local companion** runtime on
the user's Mac registers itself with the web shell (S24), and the browser talks
to it for MLX-bound work: train, fuse, export, serve. Hardware use is gated by
an explicit, scoped, revocable permission prompt (S25). Data split: models,
artifacts, and user memory stay on the device; the hosted side keeps only
account + metadata (S26).

**Pros**
- Matches the north star exactly: web-app ease, local compute + data.
- Distribution is a URL, not a DMG — install friction mostly hits the optional
  companion, not first contact.
- Reuses everything that exists: web shell (S21), auth, lanes, hardening.
- Keeps the hosted product open even while training runs (status, compare with
  hosted columns, dataset curation on any device).
- Clear revocation story: kill the bridge token in the UI; companion stops
  serving.

**Cons**
- Two moving parts: pairing, version skew between shell and companion, and a
  local HTTPS/loopback endpoint the browser must reach (mixed-content rules on
  an https shell — needs loopback exception handling or the companion serves
  over `localhost` with proper cert story).
- New security surface: a daemon on the user's machine that accepts remote
  intent → the S25 prompt + scoped tokens + artifact-hash pinning are mandatory,
  not optional.
- Support complexity: failures can now be hosted-side, device-side, or the
  bridge.

### Option B — Full local-first (everything installed, Ollama/Unsloth-style)

One download: runtime + UI bundled on the Mac; `llmtuner up` opens the browser
app; no hosted side at all (or the VPS becomes an optional team add-on).

**Pros**
- One trust boundary, no pairing/bridge protocol to secure; offline by default.
- Already ~80% real today: CLI + `.app` bundle + menu bar (S2/S6/S7) exist.
- Zero ongoing hosting cost; total data locality.

**Cons**
- Kills the URL-first funnel: sign-up, sharing, team lanes, hosted compare
  columns, and the deployed-demo that Phase 5 just shipped (S21/#24) all need a
  local substitute or vanish.
- Update friction: every fix is a re-download; the daily-train velocity becomes
  invisible to users.
- Multi-user/team use (the VPS's whole point since #20/H2) is not solved.
- First contact requires installing something — the exact friction the north
  star calls out as the product gap.

## Decision

**Recommend Option A (hybrid).** Rationale:

1. It is the only option that satisfies both halves of the north star — web
   ease *and* local compute/data — while B satisfies only locality.
2. The October train already commits to A's skeleton: S23 installer, S24
   companion, S25 bridge, S26 data split. Choosing B would cancel four
   scheduled slices and orphan S21's deployed shell.
3. A degrades gracefully to B: the companion is `llmtuner up` grown up, and if
   the hosted side is down, the local path still trains and compares locally.
4. B's only hard advantage (single trust boundary) is addressed in A by making
   the bridge explicitly opt-in, scoped, and revocable (S25) — a constraint we
   should impose anyway before inviting shared use.

**This ADR is Proposed, not Accepted**: it is the lane's recommendation, and
the decision belongs to Carlos. Accept = comment "accepted" on #25 (the lane
then flips Status to Accepted here); reject = say so on #25 before S24 (10-12)
lands, and the train reorders around B.

## Consequences

If adopted (A):
- Must build: companion registration/pairing flow (S24), permission prompt +
  scoped/revocable tokens (S25), metadata-only hosted DB (S26), one-command
  installer for the runtime (S23).
- Must decide, before S24 design lands: companion transport (loopback HTTP vs
  WebSocket dial-out from the Mac — dial-out avoids NAT/mixed-content issues
  and is the lane's implicit lean).
- Hosting cost and abuse surface stay (S21 hardening checklist applies:
  HTTPS, firewall, JWT rotation).
- Docs to follow: architecture page update, USER_STORIES for the fresh-install
  path, and a bridge threat-model note in CREDENTIALS.md.

If rejected (B):
- S24–S26 are cancelled or repurposed as "companion grows into the whole app";
  S21's shell becomes an internal/team tool rather than the public funnel;
  update/distribution story (S23) becomes the primary product surface.
