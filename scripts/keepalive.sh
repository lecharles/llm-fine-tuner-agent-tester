#!/usr/bin/env bash
# LLM Tuner VPS team-instance keepalive (:8090).
# Usage: keepalive.sh check|start|stop|status
REPO="/home/hermes/llm-fine-tuner-agent-tester"
LOG="/tmp/llmtuner-keepalive.log"
PORT=8090
healthy() {
  curl -sf --max-time 5 "http://localhost:$PORT/health" >/dev/null
}
start_it() {
  cd "$REPO/backend" || return 1
  set -a; . /home/hermes/llmtuner-vps/env; set +a
  .venv-smoke/bin/python -m uvicorn main:app --host 0.0.0.0 --port "$PORT" >> "$LOG" 2>&1 &
  disown
}
case "${1:-check}" in
  status) healthy && echo "UP" || echo "DOWN";;
  stop)   pkill -f "uvicorn main:app --host 0.0.0.0 --port $PORT" && echo stopped || echo "not running";;
  start)  start_it && echo starting;;
  check)
    if healthy; then exit 0; fi
    echo "$(date -u +%FT%TZ) DOWN -> restarting" >> "$LOG"
    pkill -f "uvicorn main:app --host 0.0.0.0 --port $PORT"
    sleep 2
    start_it
    sleep 6
    healthy && echo "$(date -u +%FT%TZ) recovered" >> "$LOG" || echo "$(date -u +%FT%TZ) STILL DOWN after restart" >> "$LOG"
    ;;
esac
