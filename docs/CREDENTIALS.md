# Credential Rotation

Shared-instance hardening deliverable from S15 (issue #17). Everything here
uses placeholder values — never paste real secrets into this repo, an issue,
or a terminal log.

## Where secrets live

| Scope | File | Notes |
|-------|------|-------|
| Developer checkout | `backend/.env` | never commit it; it stays git-ignored |
| Installer / local app | `~/.llmtuner/.env` (`LLMTUNER_HOME`) | wins over `backend/.env` on read |
| VPS team instance (`:8090`) | `/home/hermes/llmtuner-vps/env` | sourced by `scripts/keepalive.sh` |

Rotation = edit the file, restart the process, verify. The keepalive
restarts the backend within ≤10 min anyway; to force it:
`bash scripts/keepalive.sh stop && bash scripts/keepalive.sh start`.

## 1. JWT signing secret (`JWT_SECRET_KEY`)

Signs every login token. Rotate when someone with access leaves, when a
value may have leaked, or on any suspicion of token forgery.

1. Generate a fresh secret: `python3 -c "import secrets; print(secrets.token_hex(32))"`
2. In the env file: `JWT_SECRET_KEY=<new-value>` (replace the whole line).
3. Restart the backend. **All existing sessions are invalidated** — users
   are bounced to login; that is the point of the rotation.
4. Verify: log in (`POST /api/auth/login` → 200) and confirm an old token
   now fails (`GET /api/auth/me` with the pre-rotation token → 401).

The default value is a dev placeholder; a shared instance must never run on it.

## 2. Service lane tokens (`API_SERVICE_TOKENS`)

`lane:token` pairs used by the tmux lanes (S8). Rotate per-lane — replace
only that lane's token — or wholesale:

1. New tokens: `openssl rand -hex 24` per lane.
2. Update the pair list, e.g. `API_SERVICE_TOKENS=tmux-hermes:<new>,tmux-opencode:<new>`.
3. Restart, then smoke one lane:
   `curl -s -H "Authorization: Bearer <new>" https://…/api/status | head -c 200`
   → expect that lane's identity block.
4. Old tokens die with the restart (they are not persisted anywhere). Tell
   every lane operator to pull the new value from the env file owner.

## 3. Provider API keys (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`)

Rotate at the provider's console first (revoke there, mint the replacement),
then drop the new value into the env file and restart. Generation falls
back down the ladder (hosted → hosted → local Ollama) while a key is
missing, so a brief gap is survivable. Verify with one quick generation
from the Compare page or `POST /api/chat/sessions`.

## 4. User passwords / "resetting" a login

Normal path: the user changes their own password via the app UI. If someone
is locked out of the shared instance, an operator resets it in the DB:

```bash
cd backend && .venv-smoke/bin/python - <<'PY'
from database import SessionLocal
from models.user import User
from core.security import hash_password
db = SessionLocal()
u = db.query(User).filter(User.email == "carlos@example.com").first()
u.hashed_password = hash_password(input("new password: "))
db.commit(); print("reset", u.email)
PY
```

The script prompts at the terminal, so the password never lands in shell
history or logs. The `local@llmtuner` bootstrap user only exists on a
`LOCAL_MODE` install.

## 5. The `LOCAL_MODE` guard (S15)

`LOCAL_MODE=true` skips login for everyone who can reach the port — safe
only on loopback. Two hard refusals now enforce that:

- **Startup:** `LOCAL_MODE=true` + `uvicorn --host 0.0.0.0` (or any
  non-loopback bind) exits with `Refusing to start: LOCAL_MODE=true
  requires a loopback bind…`. The Mac CLI binds `127.0.0.1` and is
  unaffected.
- **Runtime:** a running `LOCAL_MODE` instance answers `403` to every
  non-loopback peer (except `/health`, kept open for monitors), covering
  bind paths the startup sniff can't see.

The VPS team instance must run **without** `LOCAL_MODE`. If you need a
throwaway account on it: signups are throttled to
`SIGNUP_RATE_LIMIT_PER_HOUR` per IP (default 1/hour, 429 + `Retry-After`
beyond that) — raise it temporarily in the env file for planned onboarding,
then put it back.

## Rotation cadence

- JWT secret + lane tokens: quarterly, and immediately on team changes or leaks.
- Provider keys: per provider policy or on leak suspicion.
- Locked-out user resets: on request (log who reset what when).
