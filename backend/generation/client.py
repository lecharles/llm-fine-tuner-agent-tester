"""Call an LLM with a forced-JSON tool and a quality fallback ladder.

Generation defaults to Anthropic Fable (top quality) and falls back to Opus 4.8, then Sonnet 5, if
a call fails or returns nothing usable. All three are Anthropic models, so this is one SDK and one
code path across three tiers. Structured output is forced with a tool whose input_schema is the
shape we want back, so the reply is valid JSON we can use directly instead of parsing free text.

Model IDs and prompting strategy: see docs/RESEARCH_DATASETS.md.
"""

from anthropic import Anthropic

MODEL_LADDER = ["claude-fable-5", "claude-opus-4-8", "claude-sonnet-5"]

_client: Anthropic | None = None


def _get_client() -> Anthropic:
    """One shared client, created lazily. The key is read from ANTHROPIC_API_KEY in the
    environment by the SDK, never from the database or the request."""
    global _client
    if _client is None:
        _client = Anthropic()
    return _client


def call_json_tool(
    system: str,
    user: str,
    tool_name: str,
    input_schema: dict,
    max_tokens: int = 4096,
) -> dict:
    """Call the model with one forced tool and return the tool's input, a dict matching
    input_schema. Walks the model ladder top to bottom: the first tier that returns a usable
    tool call wins, and any error or empty result falls through to the next tier. Raises if
    every tier fails, so the caller can surface a clean error."""
    client = _get_client()
    tool = {
        "name": tool_name,
        "description": "Return the result using this structure.",
        "input_schema": input_schema,
    }
    failures = []
    for model in MODEL_LADDER:
        try:
            response = client.messages.create(
                model=model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
                tools=[tool],
                tool_choice={"type": "tool", "name": tool_name},
            )
            for block in response.content:
                if block.type == "tool_use" and block.name == tool_name:
                    return block.input
            failures.append(f"{model}: no tool_use in response")
        except Exception as exc:
            failures.append(f"{model}: {exc}")
    raise RuntimeError("All generator models failed: " + "; ".join(failures))