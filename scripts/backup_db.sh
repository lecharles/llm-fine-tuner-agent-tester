#!/usr/bin/env bash
# S46 — online SQLite backup + rotation for the :8090 app DB (~/.llmtuner/app.db).
#
# Uses SQLite's online backup API (same mechanism as the sqlite3 CLI's `.backup`),
# so the snapshot is consistent even while the backend is writing. No server
# stop required. Snapshots are written OUTSIDE the repo and chmod 600 — the DB
# holds user rows and account metadata; snapshots inherit that sensitivity.
#
# Env overrides:
#   LLMTUNER_DB         source DB            (default $HOME/.llmtuner/app.db)
#   LLMTUNER_BACKUP_DIR snapshot directory   (default $HOME/.llmtuner/backups)
#   LLMTUNER_BACKUP_KEEP snapshots to retain (default 14 — daily cron = 2 weeks)
#   LLMTUNER_PY         python3 with sqlite3 (default python3)
#
# Exit 0 + "backup_db: ok ..." on success; non-zero + stderr on any failure.
set -euo pipefail

DB="${LLMTUNER_DB:-$HOME/.llmtuner/app.db}"
BACKUP_DIR="${LLMTUNER_BACKUP_DIR:-$HOME/.llmtuner/backups}"
KEEP="${LLMTUNER_BACKUP_KEEP:-14}"
PYBIN="${LLMTUNER_PY:-python3}"

[ -f "$DB" ] || { echo "backup_db: no DB at $DB" >&2; exit 1; }
command -v "$PYBIN" >/dev/null 2>&1 || { echo "backup_db: python binary '$PYBIN' not found" >&2; exit 1; }

umask 077
mkdir -p "$BACKUP_DIR"
STAMP="$(date -u +%Y%m%d-%H%M%S)"
OUT="$BACKUP_DIR/llmtuner-app-$STAMP.db"

# 1) Online backup. sqlite3 CLI if present, else the identical Python API.
if command -v sqlite3 >/dev/null 2>&1; then
  sqlite3 "$DB" ".backup '$OUT'"
else
  "$PYBIN" - "$DB" "$OUT" <<'PY'
import sqlite3, sys
src, dst = sys.argv[1], sys.argv[2]
with sqlite3.connect(src) as s, sqlite3.connect(dst) as d:
    s.backup(d)
PY
fi

# 2) Integrity-check the COPY before trusting it.
CHECK="$("$PYBIN" - "$OUT" <<'PY'
import sqlite3, sys
con = sqlite3.connect(sys.argv[1])
print(con.execute("PRAGMA integrity_check").fetchone()[0])
con.close()
PY
)"
if [ "$CHECK" != "ok" ]; then
  echo "backup_db: integrity_check FAILED on $OUT ($CHECK)" >&2
  exit 1
fi
chmod 600 "$OUT"

# 3) Rotate: keep the newest $KEEP snapshots.
ls -1t "$BACKUP_DIR"/llmtuner-app-*.db 2>/dev/null | tail -n +$((KEEP+1)) | while IFS= read -r old; do
  rm -f "$old"
done

SIZE="$(stat -c%s "$OUT" 2>/dev/null || "$PYBIN" -c 'import os,sys;print(os.path.getsize(sys.argv[1]))' "$OUT")"
echo "backup_db: ok $OUT ($SIZE bytes, integrity ok, keeping newest $KEEP)"
