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

## Data split (S26, issue #29): bytes stay on the Mac

Phase 6 rule: the hosted database owns the **account** (users, datasets,
Q&A pairs, chat, run history, these grants) and only ever **metadata
pointers** to device artifacts — adapters, fused models, GGUFs, train logs.

- A paired companion may send `{"type":"artifacts","items":[{device_run_id,
  kind(adapter|fused|gguf|trainlog), name, base_model?, size_bytes?,
  sha256?, device_path?}]}` over `/companion/ws`; the hub validates it and
  replies `{"type":"artifacts_ack", ok, stored}`. Rows upsert by
  (permission, device_run_id, kind), so re-reports refresh instead of duplicating.
- `GET /api/bridge/artifacts` lists **my** pointers (with device name +
  online flag); `DELETE /api/bridge/artifacts/{id}` forgets one. Forgetting
  is pointer-only — there are no hosted bytes to delete. That is the point.
- `device_path` is display metadata. Hosted code never opens, stats, or
  serves it; no hosted endpoint accepts a device path as input. Existing
  `fine_tuned_models.gguf_path` rows from pre-split training were created by
  on-device (LOCAL_MODE) backends, where the path IS local — and the
  instance-wide `local_mode` gate (H3 + bind guard) is what keeps that true.

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
  the S26 pointer ledger (`device_artifacts`) ships with this train, and the
  companion-side `artifacts` emitter that feeds it is the next companion
  slice (the hub already accepts and acks the frame — see the S26 test).
- Companion reconnects supersede an older session on the same grant
  (close code 4009) rather than racing two sockets.
