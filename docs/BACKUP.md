# BACKUP — :8090 app database (S46)

One-command online backup + rotation for the live SQLite DB, plus a tested
restore drill. Script: `scripts/backup_db.sh` (repo), snapshots under
`~/.llmtuner/backups/` (outside the repo — never commit these).

## What gets backed up

`~/.llmtuner/app.db` — users, datasets, QA pairs, training runs + persisted
error text, fine-tuned model metadata, chat sessions, bridge permissions,
device artifact pointers, alembic version. The snapshot uses SQLite's online
backup API (the same mechanism as `sqlite3 .backup`), so it is consistent even
while the backend is writing. No server stop, no `-wal` games.

## Manual run

```bash
bash /home/hermes/llm-fine-tuner-agent-tester/scripts/backup_db.sh
# expected: backup_db: ok /home/hermes/.llmtuner/backups/llmtuner-app-<UTC stamp>.db (NNN bytes, integrity ok, keeping newest 14)
```

Tunables via env: `LLMTUNER_DB`, `LLMTUNER_BACKUP_DIR`, `LLMTUNER_BACKUP_KEEP`
(default 14), `LLMTUNER_PY`. The script integrity-checks every snapshot
(`PRAGMA integrity_check`) and only then rotates.

## Cron (installed)

Daily 04:00 UTC, flock-guarded like the keepalive line, logged:

```
0 4 * * * /usr/bin/flock -n /tmp/llmtuner-backup.lock bash /home/hermes/llm-fine-tuner-agent-tester/scripts/backup_db.sh >> /home/hermes/.llmtuner/backups/backup.log 2>&1
```

Verify with `crontab -l`; first scheduled result appears in `backup.log`.

## Restore drill (tested 2026-11-06 UTC)

Procedure:

1. Pick the newest snapshot: `ls -1t ~/.llmtuner/backups/llmtuner-app-*.db | head -1`
2. Stop the backend (Ctrl-C the process keepalive supervises, or let the restart below do it) and restore to a **scratch copy first**: `cp <snapshot> /tmp/restore-check.db`, then `PRAGMA integrity_check` and row-count spot checks before touching the live file.
3. Real restore: stop the :8090 backend (the restart runbook in
   `docs/PUBLIC-INSTANCE.md` names the process), `cp <snapshot>
   ~/.llmtuner/app.db` (default path is `$LLMTUNER_HOME/app.db`, overridable
   via `LLMTUNER_DB`), then start it again — keepalive also probes `/health`.
4. Verify: `curl -s http://127.0.0.1:8090/health` → `{"status":"ok"}`; log in; check the Datasets list.

Drill actually executed on 2026-11-06: snapshot
`llmtuner-app-20261106-175833.db` (2,641,920 bytes) → file-level restore to a
scratch path → `PRAGMA integrity_check` = ok → row counts matched the live DB
exactly (users 4, datasets 7, qa_pairs 1052, training_runs 1, others 0,
alembic_version 1). Rotation logic verified separately (KEEP=2, three runs →
newest two kept). Live DB was never overwritten during the drill.

## Security

- Snapshots are chmod 600, dir 700 (umask 077). They contain user rows and
  account metadata — treat them like secrets. Never commit them, never copy
  them into the repo tree.
- Optional off-box copy (run from wherever the destination key lives):
  `scp ~/.llmtuner/backups/llmtuner-app-*.db carlos@elsewhere:llmtuner-backups/`

## Scope note

The row's `deploy/` path is still root-owned on the VPS; the lane could not
place anything there (pending Carlos's one-time
`sudo chown -R hermes:hermes deploy/`). Everything this slice needs therefore
lives in `scripts/` + `docs/` — the docs-only fallback the row explicitly
allows.
