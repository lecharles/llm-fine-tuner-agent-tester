"""Call an LLM with a forced-JSON tool and a quality fallback ladder.

Generation walks a cross-provider ladder. It prefers Anthropic (Fable -> Opus
4.8 -> Sonnet 5), and when every Anthropic tier fails or no Anthropic key is
configured, it continues into OpenAI (gpt-4o-mini -> gpt-5.5). One provider
being out of credit therefore does not sink a generation: it falls through to
the other account that has balance.

Structured output is forced with a tool whose input_schema is the shape we
want back, so the reply is valid JSON we can use directly instead of parsing
free text. Each provider uses its own SDK's tool-forcing shape, but callers
see one uniform dict either way.

Model IDs and prompting strategy: see docs/RESEARCH_DATASETS.md.
"""

import json
import os

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


def call_json_tool(
    system: str,
    user: str,
    tool_name: str,
    input_schema: dict,
    max_tokens: int = 4096,
) -> dict:
    """Force one tool call and return its input, a dict matching input_schema.

    Walks the Anthropic ladder, then the OpenAI ladder. The first tier that
    returns a usable tool call wins; any error or empty result falls through.
    Raises a single error listing every tier's failure, so the caller surfaces
    one clean message covering both providers."""
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

    if anthropic is None and openai is None:
        raise RuntimeError(
            "No generator API keys configured. Add ANTHROPIC_API_KEY and/or "
            "OPENAI_API_KEY to ~/.llmtuner/.env and restart `llmtuner up`."
        )
    raise RuntimeError("All generator models failed: " + "; ".join(failures))
