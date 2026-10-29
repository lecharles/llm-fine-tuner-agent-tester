# ADR-002 — API Agents extraction: boundary map + import cuts

- **Date:** 2026-10-29 (shipped late from the 10-26 row)
- **Status:** Proposed (lane recommendation; sign-off via the next issue thread)
- **Deciders:** Carlos (final call), commit-train lane (drafting)
- **Related:** S41 (scheduled 10-27, still TODO — provider-client layer split into
  its own package/module), docs/ADR-001-phase6-hybrid-vs-local-first.md,
  S8 (`API_SERVICE_TOKENS`), S13 (compare column pickers), S28 (fan-out),
  S37/S38 (model-family registry)

## Context

The repo is called *LLM Fine Tuner & **Agent Tester***. The agent-testing half —
anything that talks to an LLM API (hosted OpenAI/Anthropic, local Ollama, the
fine-tuned model served on a loopback port) — has grown inside the tuner's
backend. It is now a coherent, separately-testable product surface: a fallback
ladder, four-way compare fan-out, structured tool-call generation, and a model
registry. Before Phase 6 (ADR-001) builds more bridges on top of it, draw the
line: what belongs in an `api-agents` package/repo, what stays with the tuner,
and where the import cuts go.

Today the coupling looks like this (all paths relative to `backend/`):

| Module | Role | Touched by |
|--------|------|-----------|
| `generation/client.py` | provider SDKs + fallback ladder (`call_json_tool`, `OPENAI_LADDER`, `ANTHROPIC_LADDER`, Ollama HTTP) | `generation/qa_generator.py`, `routers/generation.py` |
| `chat/client.py` | plain `chat_completion` for compare columns | `chat/compare.py` |
| `chat/compare.py` | `Backend`/`Reply` model, hosted/local/ollama backend builders, `fan_out` (S28) | `routers/chat.py` |
| `chat/local_server.py` | spawn/ensure loopback servers for fused/base models | `routers/chat.py` |
| `generation/local_registry.py` | model-family recipes + prefer_order (S37/S38) | `generation/client.py`, `generation/status.py` |
| `generation/status.py` | "is Ollama up / which models installed" | `routers/status.py`, `routers/generation.py` |

…while the tuner side owns: accounts/auth (`core/security.py`, `routers/auth.py`),
persistence (`models/`, `schemas/`, `alembic/`), datasets & Q&A pairs, training
(`training/`), the S25 bridge hub, and the SPA shell (`static_serve.py`).

## Decision

**Extract `api-agents` as a first-party package (in this repo, under
`backend/api_agents/`), not a separate git repo yet.** One repo, two clearly
cut layers; revisit a split repo only if a second consumer appears (e.g. the
Mac companion shipping its own agent test CLI). This is what S41 implements.

### Boundary map — what lives where

**api-agents (the extracted package):**

- Provider clients: OpenAI, Anthropic, Ollama HTTP — ladder resolution and
  per-column model pickers (S13) included.
- The fallback ladder itself + structured-output `call_json_tool` (agent-test
  entrypoint).
- Compare primitives: `Backend`, `Reply`, `hosted_backends/local_backends/
  ollama_backend`, `fan_out`.
- Model-family registry (`local_registry`) + local-model probe/status.
- Loopback server ensure (`local_server`) behind a narrow
  `ServerLauncher` protocol, so tests can fake it.

**Stays in the tuner backend:**

- Everything SQL: models, schemas, migrations, owner-or-public authz (S31).
- Auth/session machinery, rate limits, lane tokens (S8), bind guard (S15).
- Training runner, dataset import, prompt suggest (tuner-specific semantics).
- Bridge hub (S25/S26) and the SPA.
- `ANSWER_CAP` product policy and chat persistence — api-agents returns raw
  replies; routers decide what a "chat message" is.

### Import cuts (the contract)

1. `backend/api_agents/__init__.py` exports exactly:
   `call_json_tool`, `chat_completion`, `hosted_backends`, `local_backends`,
   `ollama_backend`, `fan_out`, `installed_ollama_models`,
   `local_model_status`, `prefer_order` — nothing else is stable API.
2. api-agents may import stdlib + provider SDKs + `config` (read-only env).
   It must **never** import `models.*`, `schemas.*`, `database`, or
   `core.security`. (Enforce in S41: a tests/ grep-based guard test.)
3. Callers inject credentials/limits as arguments (keys from env stay resolved
   inside the package, but per-request `max_tokens`/system prompt come from
   the caller). No ambient DB session crosses the boundary.
4. Routers keep building DB-backed state, then call api-agents and persist
   the result — one direction only.

### Options considered

- **A. Separate repo now.** Full package/PyPI ceremony, version skews between
  the two halves, and the daily lane would spend its budget on release
  plumbing. Only justified by a second consumer — none exists. **Rejected.**
- **B. In-repo package with import cuts** (chosen). Cheapest honest boundary:
  rename-free move of the 6 modules above, a re-export `__init__`, and a CI
  guard test. Trivially promotable to its own repo later — the boundary *is*
  the cut line.
- **C. Do nothing / status quo.** The ladder, fan-out and registry are exactly
  what the Mac companion (S24) will need to import without dragging FastAPI
  and SQLAlchemy onto the device. Deferred extraction keeps re-using the
  Phase-6 problem ADR-001 just solved. **Rejected.**

## Consequences

- S41 becomes: move `chat/{client,compare,local_server}.py` +
  `generation/{client,local_registry,status}.py` under `backend/api_agents/`,
  add the re-export barrel, update imports in `routers/*` and
  `generation/qa_generator.py`, and land the guard test (rule 2) in `tests/`.
  Behavior-preserving only; no feature work rides along.
- The S24 companion can then import `api_agents` directly against the
  on-device Ollama/fine-tuned server without the web stack.
- `tests/test_model_families_s38.py` fakes patch module paths — S41 must
  re-point those patches in the same commit, or the suite catches it.
- Provider API keys keep resolving from env inside the package; docs must not
  and do not contain real keys (house rule).
- Risk: two import sites per module during the move (e.g. `generation.client`
  in monkeypatch strings) — mitigated by running the full pytest suite as the
  cut's definition of done.

## Verification recipe (for S41, prep now)

1. `git grep -n "generation\.client\|chat\.compare" backend tests` → expect
   only the new `api_agents` paths after the move.
2. `python3 -m py_compile` on every touched file + fresh `import main` smoke.
3. `pytest -q` green (current: 110 tests).
4. Manual: POST `/api/chat/compare` on :8090 returns four columns as before.
