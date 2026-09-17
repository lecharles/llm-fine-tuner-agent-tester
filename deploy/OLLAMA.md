# Ollama on VPS (S3 — 2026-09-17)

VPS team instance now has local generation via Ollama. Hosted keys remain primary; Ollama is the free fallback when both Anthropic/OpenAI are empty or unconfigured.

## Install (one-time, on Ubuntu VPS)

```bash
curl -fsSL https://ollama.com/install.sh | sh
# systemd service at /etc/systemd/system/ollama.service, API on 127.0.0.1:11434
sudo systemctl enable --now ollama
ollama --version   # 0.34.1 on 2026-09-17
```

Pulled model:

```bash
ollama pull llama3.2:1b   # 1.3 GB, Q8_0, 1.2B params, context 131k
ollama list               # -> llama3.2:1b baf6a7...
curl -s http://localhost:11434/api/tags | jq .
```

## VPS env

`/home/hermes/llmtuner-vps/env`:

```
LLMTUNER_HOME=/home/hermes/.llmtuner
JWT_SECRET_KEY=<rotated>
OLLAMA_BASE_URL=http://localhost:11434
```

`backend/config.py` already exposes `ollama_base_url` (default `http://localhost:11434`) and `generation_local_models` (empty = auto-discover via /api/tags). No code change needed; restart picks up the env.

Restart:

```bash
sudo -u hermes bash scripts/keepalive.sh stop
sudo -u hermes bash scripts/keepalive.sh start
sudo -u hermes bash scripts/keepalive.sh status  # UP
curl -s http://localhost:8090/health  # {"status":"ok"}
```

## Smoke tests (verified 2026-09-17 03:42 UTC)

Direct Ollama:

```bash
curl -s http://localhost:11434/api/generate -d '{"model":"llama3.2:1b","prompt":"Say hello","stream":false}'
# {"response":"Hello.", ... "eval_count":3}

curl -s http://localhost:11434/api/chat -d '{"model":"llama3.2:1b","messages":[{"role":"user","content":"Say hello"}],"stream":false}'
# {"message":{"role":"assistant","content":"Hello."}, ...}
```

Backend ladder (Python, with VPS env loaded):

```bash
cd backend && set -a; . /home/hermes/llmtuner-vps/env; set +a
.venv-smoke/bin/python -c "
from generation.client import _ollama_available, _ollama_local_models, call_json_tool
assert _ollama_available()
assert 'llama3.2:1b' in _ollama_local_models()
r = call_json_tool(system='You generate training data...', user='Use case: coffee shop FAQ. Generate 2 pairs...', tool_name='emit_qa_pairs', input_schema={...}, max_tokens=800)
print(r)
# -> {'pairs': [{'question': 'What is the most popular drink...', 'answer': '...'}, ...]}
"
```

End-to-end generation still goes through the existing ladder (Anthropic -> OpenAI -> Ollama). With no hosted keys on the VPS, it now falls through to `llama3.2:1b` and returns structured JSON.

## Notes

- CPU-only (no GPU on this VPS); generation ~3.5s for a short hello, ~5-8s for 2 Q/A pairs.
- `keepalive.sh` still guards :8090; `ollama serve` is guarded by systemd (`ollama.service`).
- To add models: `ollama pull <model>`; to pin generation to a subset: set `GENERATION_LOCAL_MODELS=llama3.2:1b,qwen2.5:1.5b` in the VPS env and restart.
