#!/usr/bin/env bash
# S5 (#8): Icon pipeline — frontend/public/favicon.svg -> AppIcon.icns
#
# macOS-only (uses sips + iconutil). Converts the SVG to a 1024x1024 master
# PNG, emits the full iconset grid (16/32/64/128/256/512/1024 incl. @2x),
# and packages build/AppIcon.icns. Idempotent: safe to re-run, overwrites
# previous output.
#
# Usage:
#   scripts/make_app_icon.sh [output.icns]
# Default output: <repo>/build/AppIcon.icns
#
# The resulting AppIcon.icns is consumed by `llmtuner bundle` (issue #9)
# and the future menu-bar extra (issue #7).
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="$REPO/frontend/public/favicon.svg"
OUT="${1:-$REPO/build/AppIcon.icns}"
WORK="$REPO/build/appicon.iconset"

if [ "$(uname -s)" != "Darwin" ]; then
  echo "error: make_app_icon.sh requires macOS (sips/iconutil). Run it on the Mac." >&2
  exit 2
fi
if [ ! -f "$SRC" ]; then
  echo "error: source SVG not found: $SRC" >&2
  exit 1
fi

# Idempotent: start from a clean work dir and overwrite any previous output.
rm -rf "$WORK"
mkdir -p "$WORK" "$(dirname "$OUT")"

MASTER="$REPO/build/appicon-master-1024.png"
rm -f "$MASTER"

# Rasterize SVG -> 1024 PNG. sips handles SVG on recent macOS; fall back to
# qlmanage thumbnails if sips chokes on the vector source.
if ! sips -s format png "$SRC" --out "$MASTER" -Z 1024 >/dev/null 2>&1 || [ ! -s "$MASTER" ]; then
  echo "note: sips could not rasterize the SVG; falling back to qlmanage"
  THUMB_DIR="$(mktemp -d)"
  qlmanage -t -s 1024 -o "$THUMB_DIR" "$SRC" >/dev/null 2>&1 || true
  THUMB="$THUMB_DIR/$(basename "$SRC").png"
  if [ ! -s "$THUMB" ]; then
    echo "error: could not rasterize $SRC (tried sips and qlmanage)" >&2
    rm -rf "$THUMB_DIR"
    exit 1
  fi
  cp "$THUMB" "$MASTER"
  rm -rf "$THUMB_DIR"
fi

# iconutil wants the exact Apple iconset naming grid.
emit() { # emit <px> <filename>
  sips -z "$1" "$1" "$MASTER" --out "$WORK/$2" >/dev/null
}
emit 16   "icon_16x16.png"
emit 32   "icon_16x16@2x.png"
emit 32   "icon_32x32.png"
emit 64   "icon_32x32@2x.png"
emit 128  "icon_128x128.png"
emit 256  "icon_128x128@2x.png"
emit 256  "icon_256x256.png"
emit 512  "icon_256x256@2x.png"
emit 512  "icon_512x512.png"
emit 1024 "icon_512x512@2x.png"

iconutil -c icns "$WORK" -o "$OUT"

echo "ok: $OUT ($(wc -c < "$OUT" | tr -d ' ') bytes, from $SRC)"
