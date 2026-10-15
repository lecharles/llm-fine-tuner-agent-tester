# The opt-in bridge (S25, issue #28)

Phase 6's trust boundary, per `docs/ADR-001-phase6-hybrid-vs-local-first.md`:
the hosted web shell may use a user's Mac hardware **only** through an
explicit, scoped, revocable grant. Nothing else talks to a companion.

## How it works

1. **Consent** — the user opens **Bridge** in the web shell, names a device,
   and ticks the job kinds (scopes) the Mac may run:
   `status · train · fuse · export · serve`. The POST returns a one-time
   pairing token (`br1-…`); only its sha256 is stored.
2. **Pairing** — on the Mac (from `companion/`, S24):

   ```bash
   LLMTUNER_PAIRING_TOKEN=*** python companion/companion.py \
       --hub wss://<host>/companion/ws --name studio-mac
   ```

   The token travels inside the `hello` frame (never in a URL), the hub
   matches it against an *active* permission, and answers `welcome` with
   `granted_scopes`. A token with no matching active grant gets an `error`
   frame and a closed socket — there is no implicit-accept path.
3. **Scoped dispatch** — the hub only sends `job` frames whose kind is in
   the grant's scopes (`core/bridge.py`). The UI's **Probe** button exercises
   the `status` scope: job out, event stream in, exactly one result back.
4. **Revocation** — **Revoke** flips the row to `revoked`, stamps
   `revoked_at`, and force-closes the live socket on the spot (code 4001).
   A revoked token can never re-pair; the companion exits (code 2) instead
   of retry-looping. Re-pairing requires a brand-new grant.

## Where the pieces live

| Piece | File |
|-------|------|
| Grant rows (hashed token, scopes JSON, last seen/capabilities) | `backend/models/bridge.py` |
| Sessions, scope checks, job futures | `backend/core/bridge.py` |
| REST (`/api/bridge/permissions`, `…/revoke`, `…/probe`) + WS hub (`/companion/ws`) | `backend/routers/bridge.py` |
| Consent UI, token sheet, probe/revoke | `frontend/src/pages/Bridge.tsx` |
| Companion side of the protocol | `companion/companion.py` (S24) |
| Migration | `backend/alembic/versions/7e2b9c4a1f83_add_bridge_permissions.py` |

## Honest limits (for now)

- Hub state is **per-process**. One uvicorn worker serves the VPS team box
  (see `scripts/keepalive.sh`), so a plain dict is correct there; a
  multi-worker deploy must move `SESSIONS` to shared state first.
- `train`/`fuse`/`export`/`serve` dispatch through the hub exists, but the
  web shell currently wires only the read-only `status` probe to a button;
  the artifact pipeline for fine-tuned serves lands with S26 (#29).
- Companion reconnects supersede an older session on the same grant
  (close code 4009) rather than racing two sockets.
