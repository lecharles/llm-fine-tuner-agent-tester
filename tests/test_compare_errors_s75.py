"""S75 regressions: compare depth — persisted per-column errors.

Covers the self-drafted slice (ROADMAP "Compare chat depth: surface per-column
errors ... needs an error or status field on chat_messages"):
- a failed column is persisted as an assistant row with status="error" whose
  content is the same reason the live errors map carries, so the transcript
  survives a reload instead of silently dropping the column;
- the errors map keeps its old wording and precedence (a local-server startup
  failure beats the downstream connection error);
- the leak invariant from the original design note still holds the RIGHT way:
  error rows are visible in the transcript but never replayed into a column's
  model history — a recovered column continues from its last real answer.

All hermetic: in-memory SQLite, fan_out's chat_completion seam faked, no
network, no mlx_lm.server.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api_agents.chat import compare as compare_module
from core.security import get_current_user
from database import get_db
from models.fine_tuned_model import FineTunedModel
from models.user import User
from routers import chat as chat_module

BASE_MODEL = "Llama-3.2-1B"


class _Env:
    def __init__(self, client, calls, failing):
        self.client = client
        self.calls = calls       # fan_out seam log: {"model", "messages"}
        self.failing = failing   # model names that raise right now


def _history_for(env, model):
    """The messages lists the fake was called with for one column."""
    return [c["messages"] for c in env.calls if c["model"] == model]


@pytest.fixture()
def env(in_memory_db, monkeypatch):
    user = User(email="s75@mail.lmt-pytest.dev", hashed_password="x", display_name="S75")
    in_memory_db.add(user)
    in_memory_db.commit()
    in_memory_db.refresh(user)

    ft = FineTunedModel(
        user_id=user.id,
        training_run_id=1,
        name="s75-model",
        base_model=BASE_MODEL,
        gguf_path="/fake/fused_model",
    )
    in_memory_db.add(ft)
    in_memory_db.commit()
    in_memory_db.refresh(ft)

    calls = []
    failing = set()

    def fake_chat_completion(base_url, api_key, model, messages):
        calls.append({"model": model, "messages": messages})
        if model in failing:
            raise RuntimeError(f"provider down for {model}")
        return f"answer from {model}"

    monkeypatch.setattr(compare_module, "chat_completion", fake_chat_completion)
    monkeypatch.setattr(chat_module, "ensure_local_servers", lambda fused, base: {})

    app = FastAPI()
    app.include_router(chat_module.router)
    app.dependency_overrides[get_db] = lambda: in_memory_db
    app.dependency_overrides[get_current_user] = lambda: user

    with TestClient(app) as test_client:
        resp = test_client.post("/api/chat-sessions", json={
            "fine_tuned_model_id": ft.id,
            "compare_model_a": "gpt-4o-mini",
            "compare_model_b": "claude-opus-4-8",
        })
        assert resp.status_code == 201, resp.text
        test_client.session_id = resp.json()["id"]
        yield _Env(test_client, calls, failing)


def _send(env, content):
    resp = env.client.post(f"/api/chat-sessions/{env.client.session_id}/messages",
                           json={"content": content})
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_failed_column_persists_error_row_and_survives_reload(env):
    env.failing.add("gpt-4o-mini")
    turn = _send(env, "hello")

    # Live contract unchanged: errors map names the column with its reason.
    assert turn["errors"] == {"openai": "provider down for gpt-4o-mini"}

    err_rows = [m for m in turn["messages"]
                if m["role"] == "assistant" and m["status"] == "error"]
    assert len(err_rows) == 1
    assert err_rows[0]["model_label"] == "openai"
    assert err_rows[0]["content"] == "provider down for gpt-4o-mini"

    # The reload half — the actual gap this slice closes: GET shows it too.
    stored = env.client.get(f"/api/chat-sessions/{env.client.session_id}/messages").json()
    assert any(m["status"] == "error" and m["model_label"] == "openai"
               and m["content"] == "provider down for gpt-4o-mini" for m in stored)


def test_error_never_replays_into_history_after_recovery(env):
    env.failing.add("gpt-4o-mini")
    _send(env, "first question")
    env.failing.clear()
    _send(env, "second question")

    histories = _history_for(env, "gpt-4o-mini")
    assert len(histories) == 2
    # Turn 1: system + user. Turn 2: system + both user turns, no assistant
    # reply (the column never answered) and NO error text anywhere.
    assert histories[1][0]["role"] == "system"
    assert [m["content"] for m in histories[1]] == [
        histories[1][0]["content"], "first question", "second question"]
    assert all("provider down" not in m["content"] for h in histories for m in h)


def test_startup_error_wording_wins_and_is_persisted(env, monkeypatch):
    monkeypatch.setattr(chat_module, "ensure_local_servers",
                        lambda fused, base: {"fine_tuned": "local server crashed: mlx not found"})
    # Realistic pairing: the dead local server also fails the completion call.
    env.failing.add("/fake/fused_model")
    turn = _send(env, "hello")

    # Startup wording wins over "provider down for ..." in BOTH surfaces.
    assert turn["errors"]["fine_tuned"] == "local server crashed: mlx not found"
    stored = env.client.get(f"/api/chat-sessions/{env.client.session_id}/messages").json()
    row = next(m for m in stored if m["model_label"] == "fine_tuned")
    assert row["status"] == "error" and row["content"] == "local server crashed: mlx not found"


def test_clean_turn_persists_no_error_rows(env):
    turn = _send(env, "hello")
    assert turn["errors"] == {}
    assistants = [m for m in turn["messages"] if m["role"] == "assistant"]
    assert len(assistants) == 4
    assert all(m["status"] is None for m in assistants)
    # A recovered column DOES resume from its last real answer (positive
    # control for the exclusion filter: not-overfiltering).
    env.failing.add("claude-opus-4-8")
    _send(env, "again")
    anthropic_histories = _history_for(env, "claude-opus-4-8")
    contents = [m["content"] for m in anthropic_histories[-1]]
    assert "answer from claude-opus-4-8" in contents
