#!/usr/bin/env bash
# Paste-safe diagnostics for one training run. Run on the Mac, copy the whole
# output into Telegram so the VPS lane can see what the local process hit.
# Usage: scripts/collect-run-logs.sh [run-id]   (default: latest run)
set -u
ROOT="$HOME/.llmtuner/backend/_training_runs"
RUN="${1:-}"
if [ -z "$RUN" ]; then
  RUN=$(ls -1t "$ROOT" 2>/dev/null | head -1)
fi
if [ -z "$RUN" ]; then echo "no runs found under $ROOT"; exit 1; fi
echo "===== llmtuner run diagnostics ($(date -u +%FT%TZ)) run=$RUN ====="
echo "--- versions ---"
cd "$HOME/.llmtuner/backend" 2>/dev/null && .venv/bin/python -c "import mlx, mlx_lm, sys; print('python', sys.version.split()[0]); print('mlx_lm', mlx_lm.__version__)" 2>/dev/null || pip3 list 2>/dev/null | grep -iE "^mlx" || echo "versions unavailable"
echo "--- train.log (tail 40) ---"
tail -40 "$ROOT/$RUN/train.log" 2>/dev/null || echo "missing"
echo "--- fuse.log (tail 40) ---"
tail -40 "$ROOT/$RUN/fused_model/fuse.log" 2>/dev/null || echo "missing"
echo "--- adapters dir ---"
ls -la "$ROOT/$RUN/adapters" 2>/dev/null || echo "missing"
echo "--- disk ---"
df -h / | tail -1
echo "===== end diagnostics ====="
