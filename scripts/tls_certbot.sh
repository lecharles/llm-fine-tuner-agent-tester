#!/usr/bin/env bash
# S47 — Phase 2: Let's Encrypt lane script for the :8090 shell. Issues a cert
# with certbot (webroot mode; standalone fallback) and prints the paths to
# hand to the TLS terminator. NO secrets land in the repo: the private key
# stays in /etc/letsencrypt (root-owned 600); the lane only READS the public
# material into ~/.llmtuner/tls/.
#
#   DOMAIN=tuner.example.com bash scripts/tls_certbot.sh
#   bash scripts/tls_certbot.sh tuner.example.com
#
# Prereqs (see docs/EDGE-TLS.md): DNS A record for the domain -> this box,
# port 80 reachable for the http-01 challenge, certbot installed (Ubuntu:
# sudo apt-get install certbot — needs Carlos; the lane has no sudo).
# Renewal: cron `0 3 * * * certbot renew --deploy-hook '<redeploy>'`.
set -euo pipefail

DOMAIN="${DOMAIN:-${1:-}}"
[ -n "$DOMAIN" ] || { echo "usage: DOMAIN=host bash scripts/tls_certbot.sh   (or pass host as \$1)" >&2; exit 1; }
EMAIL="${TLS_CONTACT_EMAIL:-}"
WEBROOT="${TLS_WEBROOT:-/var/www/letsencrypt}"
TLS_DIR="${LLMTUNER_TLS_DIR:-$HOME/.llmtuner/tls}"
command -v certbot >/dev/null 2>&1 || {
  echo "tls_certbot: certbot not installed. Carlos one-time: sudo apt-get update && sudo apt-get install -y certbot" >&2; exit 1; }

if [ -n "$EMAIL" ]; then
  certbot certonly --webroot -w "$WEBROOT" -d "$DOMAIN" \
    --non-interactive --agree-tos -m "$EMAIL" --no-eff-email || {
    echo "tls_certbot: webroot failed (is $WEBROOT writable by root+certbot, is port 80 free?); retry standalone:" >&2
    certbot certonly --standalone -d "$DOMAIN" --non-interactive --agree-tos -m "$EMAIL" --no-eff-email; }
else
  certbot certonly --webroot -w "$WEBROOT" -d "$DOMAIN" || {
    echo "tls_certbot: webroot failed; retry standalone (port 80 must be free):" >&2
    certbot certonly --standalone -d "$DOMAIN"; }
fi

LIVE="/etc/letsencrypt/live/$DOMAIN"
[ -f "$LIVE/fullchain.pem" ] && [ -f "$LIVE/privkey.pem" ] || {
  echo "tls_certbot: cert issued but not found under $LIVE" >&2; exit 1; }

umask 077; mkdir -p "$TLS_DIR"
cp "$LIVE/fullchain.pem" "$TLS_DIR/le-fullchain.pem"
chmod 600 "$TLS_DIR/le-fullchain.pem"
echo "tls_certbot: ok. Key stays at $LIVE/privkey.pem (root 600 — never copy into the repo)."
echo "  public chain copied to $TLS_DIR/le-fullchain.pem"
echo "  next: point the chosen terminator at the pair — docs/EDGE-TLS.md Phase 2 step 4"
echo "  renewals: certbot renew (systemd timer, or add cron 0 3 * * * certbot renew --quiet)"
