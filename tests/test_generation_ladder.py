"""Fallback-ladder tests for S9 (issue #12) with every provider faked.

generation.client walks Anthropic -> OpenAI -> local Ollama. These tests pin
the walking order, the account-error tier fast-fail, and the actionable errors
for "nothing configured" and "everything failed". No network, no keys.
"""

import json

import pytest

import generation.client as gc
from generation.client import ANTHROPIC_LADDER, OPENAI_LADDER, call_json_tool


class FakeResponse:
    """Stand-in for an anthropic OpenAI-shape response object."""

    def __init__(self, blocks):
        self.content = blocks


class FakeBlock:
    def __init__(self, type_, name=None, input_=None):
        self.type = type_
        self.name = name
        self.input = input_


def _anthropic_ok(payload):
    class Client:
        class messages:
            @staticmethod
            def create(**kwargs):
                Client.last_kwargs = kwargs
                return FakeResponse([FakeBlock("text"), FakeBlock("tool_use", "make_json", payload)])

    return Client()


def _openai_ok(payload):
    call = type(
        "Call",
        (),
        {"function": type("Fn", (), {"name": "make_json", "arguments": json.dumps(payload)})()},
    )()

    class Client:
        class chat:
            class completions:
                @staticmethod
                def create(**kwargs):
                    Client.last_kwargs = kwargs
                    return type(
                        "Resp",
                        (),
                        {"choices": [type("Ch", (), {"message": type("M", (), {"tool_calls": [call]})()})]},
                    )()

    return Client()


@pytest.fixture()
def no_keys(monkeypatch):
    """Simulate both hosted providers unconfigured and Ollama unreachable."""
    monkeypatch.setattr(gc, "_get_anthropic_client", lambda: None)
    monkeypatch.setattr(gc, "_get_openai_client", lambda: None)
    monkeypatch.setattr(gc, "_ollama_available", lambda: False)
    yield monkeypatch


def test_anthropic_tool_forcing_shape(no_keys):
    client = _anthropic_ok({"answer": 42})
    out = gc._call_anthropic(client, "claude-test", "sys", "user", "make_json", {"type": "object"}, 10)
    assert out == {"answer": 42}
    assert client.last_kwargs["tool_choice"] == {"type": "tool", "name": "make_json"}
    assert client.last_kwargs["model"] == "claude-test"


def test_openai_function_forcing_shape(no_keys):
    out = gc._call_openai(_openai_ok({"ok": True}), "gpt-test", "s", "u", "make_json", {}, 10)
    assert out == {"ok": True}


def test_ladder_walks_anthropic_in_order(monkeypatch):
    seen = []

    class Dying:
        class messages:
            @staticmethod
            def create(**kwargs):
                seen.append(kwargs["model"])
                if len(seen) < 3:
                    raise RuntimeError("rate limit")
                return FakeResponse([FakeBlock("tool_use", "make_json", {"win": seen[-1]})])

    monkeypatch.setattr(gc, "_get_anthropic_client", lambda: Dying())
    monkeypatch.setattr(gc, "_get_openai_client", lambda: None)
    monkeypatch.setattr(gc, "_ollama_available", lambda: False)
    out = call_json_tool("s", "u", "make_json", {})
    assert out == {"win": ANTHROPIC_LADDER[2]}
    assert seen == ANTHROPIC_LADDER


def test_account_error_fast_fails_whole_tier(monkeypatch):
    seen = []

    class Broke:
        class messages:
            @staticmethod
            def create(**kwargs):
                seen.append(kwargs["model"])
                raise RuntimeError("Your credit balance is too low")

    monkeypatch.setattr(gc, "_get_anthropic_client", lambda: Broke())
    monkeypatch.setattr(gc, "_get_openai_client", lambda: _openai_ok({"via": "openai"}))
    out = call_json_tool("s", "u", "make_json", {})
    assert out == {"via": "openai"}
    assert seen == [ANTHROPIC_LADDER[0]]  # did NOT crawl the rest of the ladder
    assert OPENAI_LADDER[0] == "gpt-4o-mini"


def test_falls_through_to_ollama_when_hosted_empty(monkeypatch, tmp_path):
    monkeypatch.setattr(gc, "_get_anthropic_client", lambda: None)
    monkeypatch.setattr(gc, "_get_openai_client", lambda: None)
    monkeypatch.setattr(gc, "_ollama_available", lambda: True)
    monkeypatch.setattr(gc, "_ollama_local_models", lambda: ["llama3.2:1b"])
    asked = {}

    def fake_http(path, payload=None, timeout=5.0):
        asked["path"] = path
        asked["payload"] = payload
        return {"message": {"content": json.dumps({"via": "ollama", "model": payload["model"]})}}

    monkeypatch.setattr(gc, "_ollama_http", fake_http)
    out = call_json_tool("s", "u", "make_json", {"type": "object"})
    assert out == {"via": "ollama", "model": "llama3.2:1b"}
    assert asked["path"] == "/api/chat"
    assert asked["payload"]["format"] == {"type": "object"}  # structured forcing


def test_ollama_empty_content_is_an_error(monkeypatch):
    def fake_http(path, payload=None, timeout=5.0):
        return {"message": {"content": ""}}

    monkeypatch.setattr(gc, "_ollama_http", fake_http)
    with pytest.raises(RuntimeError, match="empty response from Ollama"):
        gc._call_ollama("m", "s", "u", {}, 10)


def test_nothing_configured_raises_setup_message(no_keys):
    with pytest.raises(RuntimeError, match="No generator backend available"):
        call_json_tool("s", "u", "make_json", {})


def test_partial_config_failure_names_every_tier(monkeypatch):
    # Anthropic keyless, OpenAI configured but broken, Ollama unreachable.
    monkeypatch.setattr(gc, "_get_anthropic_client", lambda: None)

    class Boom:
        class chat:
            class completions:
                @staticmethod
                def create(**kwargs):
                    raise RuntimeError(f"boom {kwargs['model']}")

    monkeypatch.setattr(gc, "_get_openai_client", lambda: Boom())
    monkeypatch.setattr(gc, "_ollama_available", lambda: False)
    with pytest.raises(RuntimeError) as exc:
        call_json_tool("s", "u", "make_json", {})
    msg = str(exc.value)
    assert "All generator models failed" in msg
    assert "no ANTHROPIC_API_KEY configured" in msg
    assert "openai/gpt-4o-mini: boom" in msg
    assert "openai/gpt-5.5: boom" in msg
    assert "ollama: not reachable" in msg


def test_ollama_local_models_prefers_env_config(monkeypatch):
    import config

    monkeypatch.setattr(config.settings, "generation_local_models", " llama3.2:1b , tinyllama ")
    assert gc._ollama_local_models() == ["llama3.2:1b", "tinyllama"]

    monkeypatch.setattr(config.settings, "generation_local_models", "")
    monkeypatch.setattr(
        gc, "_ollama_http", lambda path, payload=None, timeout=5.0: {"models": [{"name": "m1"}, {"nope": 1}, {}]}
    )
    assert gc._ollama_local_models() == ["m1"]

    def explode(path, payload=None, timeout=5.0):
        raise OSError("connection refused")

    monkeypatch.setattr(gc, "_ollama_http", explode)
    assert gc._ollama_local_models() == []


def test_is_account_error_markers():
    assert gc._is_account_error(RuntimeError("Your CREDIT BALANCE is too low"))
    assert gc._is_account_error(RuntimeError("invalid API key provided"))
    assert not gc._is_account_error(RuntimeError("connection reset by peer"))
