#!/usr/bin/env bash
# S47 — Phase 1: self-signed leaf cert for the :8090 shell (interim, encrypted
# path only, trust-on-first-use). Outputs live OUTSIDE the repo, chmod 600.
#
#   bash scripts/tls_selfsigned.sh [hostname-or-ip]
# default subject: the current public bind (76.13.122.86) — override as $1.
#
# After generating, the backend restart must add the two --ssl flags (see
# docs/EDGE-TLS.md Phase 1 for the exact uvicorn command). Re-running is
# idempotent (overwrites the pair). NOT trusted by browsers — Phase 2
# (Let's Encrypt via scripts/tls_certbot.sh) replaces this once DNS exists.
set -euo pipefail

SUBJ="${1:-76.13.122.86}"
TLS_DIR="${LLMTUNER_TLS_DIR:-$HOME/.llmtuner/tls}"
DAYS="${TLS_SELFSIGNED_DAYS:-825}"

umask 077
mkdir -p "$TLS_DIR"
KEY="$TLS_DIR/selfsigned.key"
CRT="$TLS_DIR/selfsigned.crt"

command -v openssl >/dev/null 2>&1 || { echo "tls_selfsigned: openssl not found" >&2; exit 1; }

# One-shot: key + CSR + self-signed cert with a SAN for the subject.
openssl req -x509 -nodes -newkey rsa:2048 -keyout "$KEY" -out "$CRT" \
  -days "$DAYS" -subj "/CN=$SUBJ/O=LLM Tuner (self-signed)" \
  -addext "subjectAltName=IP:$SUBJ,DNS:$SUBJ" 2>/dev/null ||
openssl req -x509 -nodes -newkey rsa:2048 -keyout "$KEY" -out "$CRT" \
  -days "$DAYS" -subj "/CN=$SUBJ/O=LLM Tuner (self-signed)"
# (older openssl without -addext: SAN skipped; CN still carries the name)

chmod 600 "$KEY" "$CRT"
echo "tls_selfsigned: ok $CRT + $KEY for $SUBJ (${DAYS} days, chmod 600)"
openssl x509 -in "$CRT" -noout -subject -dates -ext subjectAltName 2>/dev/null | sed 's/^/  /'
