"""S28 regressions: parallel compare fan-out.

Covers the S28 slice ("Compare: parallelize four-way fan-out instead of
sequential calls"):
- the columns are asked concurrently (a thread barrier that would deadlock a
  sequential loop is met by fake completions);
- reply order stays aligned with the backend list (the UI maps columns by
  index-sensitive code paths elsewhere);
- one column raising still degrades only that column.
"""

import threading

import pytest

from chat import compare as compare_module
from chat.compare import Backend, fan_out


def _backend(label):
    return Backend(label=label, base_url=f"http://fake/{label}", api_key="k", model=f"m-{label}")


@pytest.fixture()
def four_columns():
    backends = [_backend(f"c{i}") for i in range(4)]
    histories = {b.label: [{"role": "user", "content": "hi"}] for b in backends}
    return backends, histories


def test_fan_out_asks_all_columns_concurrently(four_columns, monkeypatch):
    backends, histories = four_columns
    # Barrier across every column: a sequential loop can never reach the
    # parties count together, so it would time out and the fake would raise.
    barrier = threading.Barrier(len(backends), timeout=5)

    def fake_chat_completion(base_url, api_key, model, messages):
        barrier.wait()
        return f"answer from {model}"

    monkeypatch.setattr(compare_module, "chat_completion", fake_chat_completion)
    replies = fan_out(backends, histories)

    assert [r.label for r in replies] == ["c0", "c1", "c2", "c3"]
    assert all(r.error is None for r in replies), [r.error for r in replies]
    assert [r.content for r in replies] == ["answer from m-c0", "answer from m-c1",
                                             "answer from m-c2", "answer from m-c3"]


def test_fan_out_keeps_order_and_isolates_failures(four_columns, monkeypatch):
    backends, histories = four_columns

    def fake_chat_completion(base_url, api_key, model, messages):
        if model == "m-c1":
            raise RuntimeError("provider down")
        return f"answer from {model}"

    monkeypatch.setattr(compare_module, "chat_completion", fake_chat_completion)
    replies = fan_out(backends, histories)

    assert [r.label for r in replies] == ["c0", "c1", "c2", "c3"]
    assert replies[1].error == "provider down"
    assert replies[1].content is None
    assert all(r.content is not None for r in replies if r.label != "c1")


def test_fan_out_empty_backends_returns_empty(four_columns):
    _, histories = four_columns
    assert fan_out([], histories) == []
