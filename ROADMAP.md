# LLM Tuner — Roadmap & Ship Plan (Sept 15–30, 2026)

Goal: a shippable v0.1.0 by Sept 30 — one-click local fine-tuning on Apple
Silicon with a team instance on the VPS, demonstrated end-to-end.

## Working today (Sept 15)

- One-port local app: `llmtuner up` serves API + UI, opens the browser only
  when `/health` answers; status splash when the UI build is missing.
- API keys load from `~/.llmtuner/.env` (installer location) — fixed.
- Local-mode auth (`/api/auth/me`) — fixed.
- Generation ladder: Anthropic → OpenAI → local Ollama (free fallback when
  both clouds are empty), with plain-English failure messages.
- QLoRA training via MLX → fuse → fine-tuned model appears under Models.
- Compare: 4 columns fan out; the two local Llama engines now auto-start on
  demand; every failed column shows its reason in-column.
- VPS team instance running on port 8090 (no MLX there; training stays Mac).

## Desktop app ask — ranked

| # | Ask | Verdict | Lane |
|---|-----|---------|------|
| D1 | `llmtuner app` opens the web UI in a floating browser-app window (Chrome `--app`, sized to the welcome page) | low-hanging | Sept 16 |
| D2 | Welcome/motivation page as the landing target for that window | low-hanging | Sept 18 |
| D3 | Icon pipeline: `frontend/public/favicon.svg` → `AppIcon.icns` (`sips`/`iconutil`) | medium | Sept 19 |
| D4 | Real `.app` bundle so the app owns the top-left menu-bar name and Dock identity | medium | Sept 20 |
| D5 | Menu-bar extra (top-right status icon: open window, server state, quit) via `rumps` | medium | Sept 21 |
| D6 | Instantiating a true tab inside an existing browser window (programmatic Safari/Chrome tab injection) | high lift; requires a browser extension per browser | backlog (Oct) |

D4 + D5 deliver the identity outcome (top-left app name, top-right menu-bar
icon) as a native app; D6 is only worth pursuing if the menu-bar app is not
enough. Needs verification on a real Mac for D3–D5; the daily lane will ship
the code and flag Mac-test checkboxes.

## Commit train (GitHub activity spread over Sept 15–30)

One slice per day, committed and pushed by an automated daily lane at
12:00 UTC. Details and definitions: [docs/COMMIT-TRAIN.md](docs/COMMIT-TRAIN.md).

Pause switch: create an empty file `PAUSE` at repo root (or tell the lane)
and no further slices are committed or pushed.

## Gates (what "done" means)

- G1 Demo run-through (Sept 18): generate → train → compare on the Mac with
  only local engines (no cloud credits). Script in docs, run before D3.
- G2 Team pings (Sept 22): each agent lane can hit the VPS instance with a
  service token, create a dataset, queue generation.
- G3 CI green (Sept 24) + v0.1.0 tag with release notes (Sept 30).

## Known constraints

- Cloud generation is blocked until Anthropic or OpenAI credit is added;
  the Ollama fallback covers the demo. VPS gets its own Ollama (Sept 17).
- MLX training requires Apple Silicon; the VPS instance runs everything
  except train/compare-local (surfaced as warnings, not crashes).
- Shared VPS instance uses real auth (no local mode); hardening lands Sept 29.
