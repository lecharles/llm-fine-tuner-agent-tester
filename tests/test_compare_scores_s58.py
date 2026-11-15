"""S58 regressions: Compare 3 — side-by-side scoring.

Covers the ledger row (backend/, frontend/ — this file is the backend half):
- PUT /api/chat-sessions/{id}/messages/{mid}/rating: 👍/👎/clear roundtrip,
  persisted and visible through GET /messages after "reload";
- only ANSWERED assistant rows are rateable: user turns 400, S75 error rows
  400, bodies outside {1, -1, null} 422, foreign/unknown messages 404;
- owner-only no-leak (S31 rule): another user's session 404s on BOTH the
  rating and the scores endpoint;
- GET /api/chat-sessions/{id}/scores: leaderboard ranks net-first, ties break
  on raw up-count then label; error rows are excluded from replies AND from
  every count (no phantom punishment); unrated-but-replied columns still show
  with net 0 so the board covers every live column.

All hermetic: in-memory SQLite, fan_out's chat_completion seam faked, no
network, no mlx_lm.server — same harness shape as tests/test_compare_errors_s75.py.
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


def _make_env(db, user, email_suffix):
    ft = FineTunedModel(
        user_id=user.id,
        training_run_id=1,
        name=f"s58-model-{email_suffix}",
        base_model=BASE_MODEL,
        gguf_path="/fake/fused_model",
    )
    db.add(ft)
    db.commit()
    db.refresh(ft)
    return ft


@pytest.fixture()
def env(in_memory_db, monkeypatch):
    owner = User(email="s58@mail.lmt-pytest.dev", hashed_password="x", display_name="S58")
    other = User(email="s58b@mail.lmt-pytest.dev", hashed_password="x", display_name="S58b")
    in_memory_db.add_all([owner, other])
    in_memory_db.commit()
    in_memory_db.refresh(owner)
    in_memory_db.refresh(other)

    ft = _make_env(in_memory_db, owner, "a")

    def fake_chat_completion(base_url, api_key, model, messages):
        return f"answer from {model}"

    monkeypatch.setattr(compare_module, "chat_completion", fake_chat_completion)
    monkeypatch.setattr(chat_module, "ensure_local_servers", lambda fused, base: {})

    app = FastAPI()
    app.include_router(chat_module.router)
    app.dependency_overrides[get_db] = lambda: in_memory_db
    app.dependency_overrides[get_current_user] = lambda: owner

    with TestClient(app) as client:
        client.owner = owner
        client.ft = ft
        resp = client.post("/api/chat-sessions", json={"fine_tuned_model_id": ft.id})
        assert resp.status_code == 201, resp.text
        client.session_id = resp.json()["id"]
        yield client


def _turn(client, content="hello"):
    resp = client.post(f"/api/chat-sessions/{client.session_id}/messages",
                       json={"content": content})
    assert resp.status_code == 201, resp.text
    return resp.json()


def _reply_id(turn, label):
    return next(m["id"] for m in turn["messages"]
                if m["role"] == "assistant" and m["model_label"] == label)


def test_rating_roundtrip_persists_and_survives_reload(env):
    turn = _turn(env)
    mid = _reply_id(turn, "fine_tuned")

    resp = env.put(f"/api/chat-sessions/{env.session_id}/messages/{mid}/rating",
                   json={"rating": 1})
    assert resp.status_code == 200, resp.text
    assert resp.json()["rating"] == 1

    # 👎 replaces 👍 (flipping a vote, not stacking), null clears.
    flip = env.put(f"/api/chat-sessions/{env.session_id}/messages/{mid}/rating",
                   json={"rating": -1})
    assert flip.status_code == 200 and flip.json()["rating"] == -1
    cleared = env.put(f"/api/chat-sessions/{env.session_id}/messages/{mid}/rating",
                      json={"rating": None})
    assert cleared.status_code == 200 and cleared.json()["rating"] is None

    # The reload half: GET /messages carries whatever the last write left.
    env.put(f"/api/chat-sessions/{env.session_id}/messages/{mid}/rating",
            json={"rating": 1})
    stored = env.get(f"/api/chat-sessions/{env.session_id}/messages").json()
    row = next(m for m in stored if m["id"] == mid)
    assert row["rating"] == 1
    # Unrated replies on the same turn expose the field as null, not missing.
    others = [m for m in stored if m["role"] == "assistant" and m["id"] != mid]
    assert others and all(m["rating"] is None for m in others)


def test_rating_rejects_user_rows_error_rows_and_bad_values(env, monkeypatch):
    turn = _turn(env)
    user_mid = next(m["id"] for m in turn["messages"] if m["role"] == "user")
    bad = env.put(f"/api/chat-sessions/{env.session_id}/messages/{user_mid}/rating",
                  json={"rating": 1})
    assert bad.status_code == 400 and "model replies" in bad.json()["detail"]

    # An S75 error row: a failure persisted as an assistant reply. Not an
    # answer, therefore not rateable.
    monkeypatch.setattr(compare_module, "chat_completion",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    failed = _turn(env, "again")
    err_mid = _reply_id(failed, "openai")
    resp = env.put(f"/api/chat-sessions/{env.session_id}/messages/{err_mid}/rating",
                   json={"rating": -1})
    assert resp.status_code == 400 and "Failed columns" in resp.json()["detail"]

    # Literal validation: anything but 1/-1/null is a 422 before the DB.
    ok_mid = _reply_id(turn, "vanilla")
    for junk in (0, 2, "up", 1.5):
        resp = env.put(f"/api/chat-sessions/{env.session_id}/messages/{ok_mid}/rating",
                       json={"rating": junk})
        assert resp.status_code == 422, (junk, resp.text)

    # Unknown message under a valid session: 404.
    resp = env.put(f"/api/chat-sessions/{env.session_id}/messages/999999/rating",
                   json={"rating": 1})
    assert resp.status_code == 404


def test_foreign_session_and_message_invisible_no_leak(env):
    # Another user's session: both endpoints answer exactly like "missing".
    other_resp = env.put("/api/chat-sessions/4242/messages/1/rating",
                         json={"rating": 1})
    assert other_resp.status_code == 404 and other_resp.json()["detail"] == "Chat session not found"
    assert env.get("/api/chat-sessions/4242/scores").status_code == 404
    # Someone else's MESSAGE id under my session also 404s (scoped lookup),
    # never "it exists but isn't yours".
    _turn(env)
    resp = env.put(f"/api/chat-sessions/{env.session_id}/messages/987654/rating",
                   json={"rating": 1})
    assert resp.status_code == 404 and resp.json()["detail"] == "Message not found"


def test_scores_leaderboard_ranks_and_counts(env):
    turn = _turn(env, "q1")
    _turn(env, "q2")
    all_msgs = env.get(f"/api/chat-sessions/{env.session_id}/messages").json()

    def rate(label, thumbs):
        """Thumb the newest unanswered reply of one column."""
        ids = [m["id"] for m in all_msgs if m["model_label"] == label]
        for i, mid in enumerate(ids):
            resp = env.put(f"/api/chat-sessions/{env.session_id}/messages/{mid}/rating",
                           json={"rating": thumbs[i % len(thumbs)]})
            assert resp.status_code == 200, resp.text

    # fine_tuned: 👍👍 (net +2). openai: 👍👎 (net 0). anthropic: 👎👎 (net -2).
    # vanilla stays unrated with 2 real replies.
    rate("fine_tuned", [1, 1])
    rate("openai", [1, -1])
    rate("anthropic", [-1, -1])

    board = env.get(f"/api/chat-sessions/{env.session_id}/scores")
    assert board.status_code == 200
    body = board.json()
    assert body["session_id"] == env.session_id
    assert body["total_rated"] == 6
    ranked = [(s["label"], s["net"], s["up"], s["down"], s["replies"], s["rated"])
              for s in body["scores"]]
    # net-first, ties broken on raw up then label; unrated-but-replied column
    # still present (the board covers every live column).
    assert ranked == [
        ("fine_tuned", 2, 2, 0, 2, 2),
        ("openai", 0, 1, 1, 2, 2),
        ("vanilla", 0, 0, 0, 2, 0),
        ("anthropic", -2, 0, 2, 2, 2),
    ]


def test_scores_exclude_error_rows_from_every_count(env, monkeypatch):
    # Turn 1 clean; then openai dies for two turns (S75 error rows land).
    _turn(env, "q1")
    def flaky(base_url, api_key, model, messages):
        if model == "gpt-4o-mini":
            raise RuntimeError("provider down")
        return f"answer from {model}"
    monkeypatch.setattr(compare_module, "chat_completion", flaky)
    _turn(env, "q2")
    _turn(env, "q3")

    board = env.get(f"/api/chat-sessions/{env.session_id}/scores").json()
    rows = {s["label"]: s for s in board["scores"]}
    assert rows["openai"]["replies"] == 1      # q1 only — the two failures are not replies
    assert rows["openai"]["rated"] == 0        # and can't be rated (endpoint 400s on them)
    assert rows["anthropic"]["replies"] == 3   # the survivor saw all three turns
    assert board["total_rated"] == 0


def test_scores_on_empty_session(env):
    body = env.get(f"/api/chat-sessions/{env.session_id}/scores").json()
    assert body == {"session_id": env.session_id, "total_rated": 0, "scores": []}
