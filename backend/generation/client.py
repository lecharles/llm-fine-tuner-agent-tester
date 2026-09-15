"""Call an LLM with a forced-JSON tool and a quality fallback ladder.

Generation walks a cross-provider ladder. It prefers Anthropic (Fable -> Opus
4.8 -> Sonnet 5), falls through to OpenAI (gpt-4o-mini -> gpt-5.5), and finally
to local Ollama if reachable. A provider being out of credit or unconfigured
therefore never sinks a generation: it falls through to the next tier, ending
on a free on-device model when both hosted accounts are empty.

Structured output is forced with a tool whose input_schema is the shape we
want back, so the reply is valid JSON we can use directly instead of parsing
free text. Each provider uses its own forcing shape (Anthropic tools, OpenAI
functions, Ollama `format` schema), but callers see one uniform dict either way.

Model IDs and prompting strategy: see docs/RESEARCH_DATASETS.md.
"""

import json
import os
import urllib.error
import urllib.request

from anthropic import Anthropic
from openai import OpenAI

from config import settings

# Provider ladder, tried in order. The first tier that returns a usable tool
# call wins. Splitting by provider lets us give each its own tool-forcing shape
# while keeping one uniform result contract for callers.
ANTHROPIC_LADDER = ["claude-fable-5", "claude-opus-4-8", "claude-sonnet-5"]
OPENAI_LADDER = ["gpt-4o-mini", "gpt-5.5"]

# Lazily built, shared clients. Rebuilt if the underlying key changes so a
# runtime edit to the .env does not strand a keyless or stale client.
_anthropic_client: Anthropic | None = None
_anthropic_key: str | None = None
_openai_client: OpenAI | None = None
_openai_key: str | None = None


def _resolve_anthropic_key() -> str | None:
    return settings.anthropic_api_key or os.environ.get("ANTHROPIC_API_KEY")


def _resolve_openai_key() -> str | None:
    return settings.openai_api_key or os.environ.get("OPENAI_API_KEY")


def _get_anthropic_client() -> Anthropic | None:
    global _anthropic_client, _anthropic_key
    api_key = _resolve_anthropic_key()
    if not api_key:
        return None
    if _anthropic_client is None or _anthropic_key != api_key:
        _anthropic_client = Anthropic(api_key=api_key)
        _anthropic_key = api_key
    return _anthropic_client


def _get_openai_client() -> OpenAI | None:
    global _openai_client, _openai_key
    api_key = _resolve_openai_key()
    if not api_key:
        return None
    if _openai_client is None or _openai_key != api_key:
        _openai_client = OpenAI(api_key=api_key)
        _openai_key = api_key
    return _openai_client


def _call_anthropic(client, model, system, user, tool_name, input_schema, max_tokens):
    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
        tools=[{
            "name": tool_name,
            "description": "Return the result using this structure.",
            "input_schema": input_schema,
        }],
        tool_choice={"type": "tool", "name": tool_name},
    )
    for block in response.content:
        if block.type == "tool_use" and block.name == tool_name:
            return block.input
    raise RuntimeError("no tool_use in response")


def _call_openai(client, model, system, user, tool_name, input_schema, max_tokens):
    response = client.chat.completions.create(
        model=model,
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        tools=[{
            "type": "function",
            "function": {
                "name": tool_name,
                "description": "Return the result using this structure.",
                "parameters": input_schema,
            },
        }],
        tool_choice={"type": "function", "function": {"name": tool_name}},
    )
    for call in (response.choices[0].message.tool_calls or []):
        if call.function.name == tool_name:
            return json.loads(call.function.arguments)
    raise RuntimeError("no tool call in response")


# --- Local Ollama fallback ------------------------------------------------
# Ollama speaks its own /api/chat with `format` set to a JSON schema, which
# forces the reply into exactly our structure. Free, offline, no credit. Uses
# stdlib urllib only so this fallback can never be blocked by a missing SDK.

def _ollama_http(path: str, payload: dict | None = None, timeout: float = 5.0):
    url = settings.ollama_base_url.rstrip("/") + path
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def _ollama_available() -> bool:
    try:
        _ollama_http("/api/version", timeout=3)
        return True
    except Exception:
        return False


def _ollama_local_models() -> list[str]:
    """Prefer generation_local_models if set, else every installed model."""
    configured = [m.strip() for m in settings.generation_local_models.split(",") if m.strip()]
    if configured:
        return configured
    try:
        tags = _ollama_http("/api/tags", timeout=3).get("models", [])
        return [t["name"] for t in tags if t.get("name")]
    except Exception:
        return []


def _call_ollama(model, system, user, input_schema, max_tokens):
    resp = _ollama_http(
        "/api/chat",
        {
            "model": model,
            "stream": False,
            "format": input_schema,          # structured output: reply matches schema
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "options": {"temperature": 0.7, "num_predict": max_tokens},
        },
        timeout=120,
    )
    content = (resp.get("message") or {}).get("content")
    if not content:
        raise RuntimeError("empty response from Ollama")
    return json.loads(content)


def call_json_tool(
    system: str,
    user: str,
    tool_name: str,
    input_schema: dict,
    max_tokens: int = 4096,
) -> dict:
    """Force one tool call and return its input, a dict matching input_schema.

    Walks the Anthropic ladder, then OpenAI, then local Ollama. The first tier
    that returns a usable structured result wins; any error or empty result
    falls through. If both hosted providers are keyless AND no Ollama is
    reachable, it raises an actionable setup message; otherwise it raises a
    single combined error naming every tier's failure."""
    failures = []

    anthropic = _get_anthropic_client()
    if anthropic is None:
        failures.append("anthropic: no ANTHROPIC_API_KEY configured")
    for model in ANTHROPIC_LADDER:
        if anthropic is None:
            break
        try:
            return _call_anthropic(anthropic, model, system, user, tool_name, input_schema, max_tokens)
        except Exception as exc:
            failures.append(f"{model}: {exc}")

    openai = _get_openai_client()
    if openai is None:
        failures.append("openai: no OPENAI_API_KEY configured")
    for model in OPENAI_LADDER:
        if openai is None:
            break
        try:
            return _call_openai(openai, model, system, user, tool_name, input_schema, max_tokens)
        except Exception as exc:
            failures.append(f"openai/{model}: {exc}")

    # Local fallback: free, on-device, no credit. Last tier, tried whenever
    # Ollama answers, including when both hosted accounts are keyless.
    if _ollama_available():
        local_models = _ollama_local_models()
        if not local_models:
            failures.append("ollama: reachable but no models installed (run `ollama pull llama3.1`)")
        for model in local_models:
            try:
                return _call_ollama(model, system, user, input_schema, max_tokens)
            except Exception as exc:
                failures.append(f"ollama/{model}: {exc}")
    else:
        failures.append("ollama: not reachable at " + settings.ollama_base_url)

    if anthropic is None and openai is None and not _ollama_available():
        raise RuntimeError(
            "No generator backend available. Add ANTHROPIC_API_KEY and/or "
            "OPENAI_API_KEY to ~/.llmtuner/.env, or start Ollama and pull a "
            "model (e.g. `ollama pull llama3.1`). Then restart `llmtuner up`."
        )
    raise RuntimeError("All generator models failed: " + "; ".join(failures))
