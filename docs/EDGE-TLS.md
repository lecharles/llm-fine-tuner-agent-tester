# EDGE-TLS — HTTPS at the edge for the :8090 shell (S47)

**Status: Proposed — needs Carlos for the two privileged steps (certbot
install, reverse-proxy install + any `sudo`).** No secrets in this repo, ever:
private keys live only in `/etc/letsencrypt/` or `~/.llmtuner/tls/` (600).

## Where we are (verified 2026-11-06)

- Shell + API served as **bare HTTP** on `0.0.0.0:8090`, public IP
  `76.13.122.86` — no TLS, no domain, self-signed path not started.
- Box state: **no nginx, no caddy, no certbot installed**; `openssl` present;
  the `hermes` lane has **no passwordless sudo** (any certbot/proxy install is
  a one-time Carlos step).
- JWT bearer tokens + signup/login credentials currently cross the wire in
  clear text. This is the last hard blocker before inviting accounts beyond
  the inner circle (ties into the `docs/PUBLIC-INSTANCE.md` hardening
  checklist and the ATS/TLS blocker named in `docs/SPIKE-REACT-NATIVE.md`).

## Decision: which edge terminator?

| | A) **Caddy** | B) nginx + certbot |
|---|---|---|
| Automatic HTTPS | built-in (issues + renews LE certs itself) | manual/certbot cron |
| Config size | 4 lines (`reverse_proxy`) | site + http-01 webroot + reload |
| Ops burden on this lane | lowest — no cert lifecycle to script | medium (renew hook, reload perms) |
| Ecosystem familiarity | newer, Go single-binary | ubiquitous |
| Websocket/stream passthrough | automatic | needs `proxy_http_version 1.1` + Upgrade headers |

**Decision: A — Caddy.** It owns the entire cert lifecycle (issue, renew,
install), which is exactly the part that rots in hand-rolled setups. The
`scripts/tls_certbot.sh` lane script is still shipped because Phase 2 step 3
below uses certbot **only in `--cert-only` handoff mode if Carlos prefers
nginx**; with Caddy, certbot is unnecessary and the script is a no-op
fallback. (The row's "certbot lane script" deliverable is satisfied either
way; no secrets in the repo in both paths.)

## Phases

**Phase 0 — today:** bare HTTP. (Done; documented.)

**Phase 1 — self-signed interim (lane can run today, no sudo needed by Carlos
for generation; restart is the only privileged-ish step):**
1. `bash scripts/tls_selfsigned.sh 76.13.122.86`
   → key + cert in `~/.llmtuner/tls/` (chmod 600).
2. Restart :8090 with `--ssl-keyfile ~/.llmtuner/tls/selfsigned.key
   --ssl-certfile ~/.llmtuner/tls/selfsigned.crt` (the keepalive restarts the
   bare-HTTP form — so this is a deliberate window, best paired with the S55
   restart runbook pass).
3. `curl -k https://76.13.122.86:8090/health` → `{"status":"ok"}`. Browsers
   will warn (self-signed = encrypted, not authenticated) — that is the point
   of an interim: credentials stop flying in the clear **now**.

**Phase 2 — Let's Encrypt (needs: a domain + one-time Carlos `sudo` steps):**
1. Carlos buys/points a DNS A record `tuner.<his-domain> → 76.13.122.86`
   (LE cannot issue for bare IPs on normal 90-day certs).
2. Carlos installs the terminator: `sudo apt-get install -y caddy`
   (or `certbot` if he chooses nginx).
3. Caddy config (root-owned, one-time Carlos step), 4 lines:
   ```
   tuner.example.com {
       reverse_proxy 127.0.0.1:8090
   }
   ```
   Caddy proves the domain on port 80, issues, renews, and terminates TLS 443
   on its own. (nginx alternative: `DOMAIN=... bash scripts/tls_certbot.sh`
   then a standard 443 server block proxying to 8090 — script prints the key
   paths; keys stay in `/etc/letsencrypt`.)
4. Rebind uvicorn to `--host 127.0.0.1 --port 8090` so **only Caddy is
   externally reachable** (this also satisfies the LOCAL_MODE-loopback design
   from S15 and the PUBLIC-INSTANCE hardening checklist).
5. Verify: `curl -sI https://tuner.example.com/health` → 200; cert valid
   (`curl -v https://tuner.example.com/health 2>&1 | grep -i "SSL certificate\|expire"`);
   http→https redirect is Caddy-default; sign-up → login → compare round-trip over TLS.
6. Announce new URL; the old `:8090` direct path disappears after step 4.

**Phase 3 — hygiene:** HSTS via Caddy (`strict_transport_security` one line),
firewall ports (allow 80/443 to Caddy only; keep 8090 loopback), and
certificate expiry alarm piggy-backed on the existing keepalive cron.

## Rollback

Each phase is one config file or one process flag: stop Caddy / drop the
`--ssl-*` flags and bare `:8090` HTTP returns unchanged. Data path is
untouched — TLS lives entirely at the edge.

## Non-goals for this slice

No app-code changes, no cert files in the repo, no DNS automation (Carlos
buys the domain), no client pinning.
