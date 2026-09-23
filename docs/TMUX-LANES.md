# TMUX Lanes — service-token auth (S8, issue #11)

Agent lanes (tmux panes driven by hermes / opencode / scripts) talk to the
VPS API with a **service token** instead of a user login. Each token is tied
to a lane name and gets read/create/queue permissions — lanes can create
datasets, queue generation, and list models, but **cannot delete** anything.

## Configuration (VPS)

In `~/.llmtuner/.env` (or the backend process env), set one comma-separated
entry per lane, `lane:token`:

```
API_SERVICE_TOKENS=tmux-hermes:REPLACE-WITH-LONG-RANDOM-A,tmux-opencode:REPLACE-WITH-LONG-RANDOM-B
```

- Generate tokens with: `openssl rand -hex 32`
- Never commit real tokens. Empty/unset = lane auth disabled.
- Restart the backend so the env is picked up.

Each lane is auto-provisioned its own service user (`lane-<name>@service.local`),
so data created by one lane is invisible to the others via the normal
per-user ownership filters.

## Endpoints

### Who am I? — `GET /api/status`

```
curl -s -H "Authorization: Bearer REPLACE-WITH-LONG-RANDOM-A" \
  https://<vps-host>/api/status
```

Expected (hermes lane):

```json
{"authenticated": true, "lane": "tmux-hermes",
 "identity": "lane-tmux-hermes@service.local",
 "permissions": ["read", "create", "queue_generation"],
 "service_lanes_configured": 2,
 "server_time_utc": "2026-09-22T...+00:00"}
```

A wrong/unknown token gets `401`, no exceptions.

### Per-lane curl recipes

Create a dataset (lane identity):

```
curl -s -X POST -H "Authorization: Bearer REPLACE-WITH-LONG-RANDOM-A" \
  -H "Content-Type: application/json" \
  -d '{"name":"hermes-smoke","description":"lane smoke","source":"manual"}' \
  https://<vps-host>/api/datasets
```

Queue generation for one of the lane's own datasets:

```
curl -s -X POST -H "Authorization: Bearer REPLACE-WITH-LONG-RANDOM-A" \
  -H "Content-Type: application/json" \
  -d '{"count":5}' \
  https://<vps-host>/api/datasets/<dataset_id>/generate
```

List the lane's datasets (other lanes' data is not visible):

```
curl -s -H "Authorization: Bearer REPLACE-WITH-LONG-RANDOM-B" \
  https://<vps-host>/api/datasets
```

Delete (must be refused for lanes):

```
curl -s -o /dev/null -w "%{http_code}\n" -X DELETE \
  -H "Authorization: Bearer REPLACE-WITH-LONG-RANDOM-A" \
  https://<vps-host>/api/datasets/<dataset_id>
```

Expected: `403 Service lanes cannot delete datasets`.

## tmux layout note

Run each lane in its own tmux window/pane with its token exported as
`LLMTUNER_LANE_TOKEN` so scripts read it from env rather than repeating
secrets on the command line:

```
tmux new-window -t lanes -n hermes
tmux send-keys -t lanes:hermes 'export LLMTUNER_LANE_TOKEN=REPLACE-WITH-LONG-RANDOM-A' C-m
```
