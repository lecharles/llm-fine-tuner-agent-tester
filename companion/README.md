# companion/ — local-device runtime (S24, issue #27)

**Status: skeleton, by design.** This is the first slice of the Phase 6 hybrid
(see `docs/ADR-001.md`). The companion process, its dial-out WebSocket
transport, pairing handshake, capability probe, local-backend bootstrap, and
the four job kinds (`status`, `train`, `fuse`, `export`, `serve`) exist and are
self-tested against a fake hub. What does **not** exist yet: the hub endpoint
(S25, issue #28 — the opt-in bridge with scoped, revocable tokens) and the
on-device artifact pipeline for serving *fine-tuned* models (S26, issue #29).
Nothing in the web shell talks to this yet.

## Why dial-out WebSocket (transport decision, per ADR-001)

- The Mac sits behind NAT/CGNAT most of the time; a loopback HTTP server on the
  device is unreachable from the hosted shell anyway.
- An https web shell cannot call `http://localhost` pages cleanly
  (mixed-content + DNS rebinding protections); an outbound wss:// dial-out
  sidesteps both.
- The pairing token travels inside the first `hello` frame, never in the URL
  (URLs land in proxy logs; frames don't).

## Running it (today: dev/self-test only)

```bash
cd ~/.llmtuner                       # or any checkout with a venv
source .venv/bin/activate            # or backend/.venv-smoke on the VPS
pip install -r companion/requirements.txt
python companion/companion.py --self-test
```

`--self-test` spins up an in-process fake hub (websockets server) + fake local
API (http.server), pairs against them, runs a full `status` + `train` +
unknown-kind job cycle asserting the event/result stream, then confirms a bad
pairing token exits with code 2 instead of retry-looping. It exits — no
leftover processes.

Real usage will be:

```bash
LLMTUNER_PAIRING_TOKEN=... python companion/companion.py \
    --hub wss://the-hub-host/companion/ws --name studio-mac
```

(`--token` also works but lands in shell history; prefer the env var.)

## Protocol (JSON frames, `llmtuner-companion/0`)

| dir | frame | meaning |
|-----|-------|---------|
| c→h | `{"type":"hello","protocol","name","token","capabilities"}` | dial-out + pair |
| h→c | `{"type":"welcome","companion_id"}` \| `{"type":"error","detail"}` | pairing result |
| h→c | `{"type":"job","id","kind","payload"}` | one of `status/train/fuse/export/serve` |
| c→h | `{"type":"event","id","stage","detail"}` | progress, many per job |
| c→h | `{"type":"result","id","ok","data"}` | exactly one per job, terminal |

`fuse` and `export` share one implementation on purpose: the shipped pipeline
(backend `training/runner.py` → `export_gguf`) currently produces the fused
bf16 model directory; real GGUF conversion is the open Phase-4 follow-up, so
both job kinds fuse the run's adapter and report the fused dir + size, with a
`note` in the result to that effect.

## What each job kind does

- **status** — capability snapshot (macOS/arch, mlx-lm importable, ollama
  present, free disk) + whether the local backend answers `/health`.
- **train** — ensures the loopback backend is up (LOCAL_MODE, auto-started
  via uvicorn on `--api`'s port if needed), POSTs `/api/training-runs`, then
  polls status + losses and streams `event` frames until the run reaches
  `completed`/`failed`. The 425 "training runs on the Mac app only" preflight
  from #42/H3 is surfaced as a clean failure result.
- **fuse / export** — re-runs the fuse step (`mlx_lm.fuse` onto the bf16 twin,
  same code path as the runner) for an existing `run_id` via a backend-module
  subprocess, so path layout stays single-sourced in `training.runner`.
- **serve** — `ollama pull <model>` + `/api/tags` verification for base
  models. Serving fine-tuned artifacts is explicitly *not* wired yet (needs
  S26); the job returns that as a readable failure, not a hang.

## Security notes (for S25 design input)

- One pairing token per companion; hub can revoke by refusing the `hello`.
  The companion treats an auth error as terminal (exit 2), not something to
  retry-loop.
- The companion only *dials out* and only ever talks to `127.0.0.1` backends +
  the configured Ollama base. It opens no listening socket.
- Jobs run arbitrary-ish work (train a given dataset on this box): S25 must
  scope tokens (which user, which device, which kinds) and the web shell must
  show an explicit permission prompt before the first job lands. Until then,
  treat `--hub` targets as fully trusted.
