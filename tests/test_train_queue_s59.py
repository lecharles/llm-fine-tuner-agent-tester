"""S59 regressions: train queue — serialize concurrent runs per user.

Guarantees covered:
- POST /api/training-runs answers 409 while the same user has an ACTIVE run
  (status "queued" or "running"), and the detail names the blocking run;
- terminal runs (completed/failed) never block a new start;
- the block is per user: another user's active run does not stop mine;
- TrainingRunOut carries queue_position: a 1-based FIFO spot among ALL
  active runs while status == "queued", and None once the run is running
  or terminal (list, detail, and the create response all stamp it);
- a rejected second start schedules NO background training task.

The runner and the MLX preflight are faked here (the VPS suite runs on
Linux, where a real preflight would 425 everything), so this tests the
queue policy, not the training itself.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.security import get_current_user
from database import get_db
from models.dataset import Dataset
from models.qa_pair import QAPair
from models.training_run import TrainingRun
from models.user import User
from routers import training_run as tr_module


@pytest.fixture()
def queue_env(in_memory_db, monkeypatch):
    # Pretend MLX is here, and swap the real runner for a call recorder —
    # background tasks must never spawn a subprocess in the suite.
    monkeypatch.setattr(tr_module, "mlx_training_available", lambda: (True, ""))
    started: list[int] = []

    def fake_run_training(run_id: int) -> None:
        started.append(run_id)

    monkeypatch.setattr(tr_module, "run_training", fake_run_training)

    users = []
    for i in range(2):
        u = User(email=f"s59-u{i}@mail.lmt-pytest.dev", hashed_password="x", display_name=f"Q{i}")
        in_memory_db.add(u)
        in_memory_db.commit()
        in_memory_db.refresh(u)
        users.append(u)

    ds = Dataset(user_id=users[0].id, name="s59-ds", description="d", source="manual")
    in_memory_db.add(ds)
    in_memory_db.commit()
    in_memory_db.refresh(ds)
    in_memory_db.add(QAPair(dataset_id=ds.id, question="q", answer="a"))
    in_memory_db.commit()

    state = {"user": users[0]}
    app = FastAPI()
    app.include_router(tr_module.router)
    app.dependency_overrides[get_db] = lambda: in_memory_db
    app.dependency_overrides[get_current_user] = lambda: state["user"]
    with TestClient(app) as client:
        yield client, {"users": users, "ds": ds, "as": lambda u: state.update(user=u), "started": started}


def _seed_run(db, user, ds, status="queued"):
    run = TrainingRun(
        user_id=user.id, dataset_id=ds.id, base_model="m", method="qlora",
        iters=10, status=status,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def test_first_start_is_201_and_schedules(queue_env, in_memory_db):
    client, ctx = queue_env
    ctx["as"](ctx["users"][0])
    r = client.post("/api/training-runs", json={"dataset_id": ctx["ds"].id})
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "queued"
    assert body["queue_position"] == 1  # alone at the head of the queue
    assert ctx["started"] == [body["id"]]


def test_second_start_while_queued_is_409(queue_env, in_memory_db):
    client, ctx = queue_env
    ds = ctx["ds"]
    first = client.post("/api/training-runs", json={"dataset_id": ds.id}).json()
    before = list(ctx["started"])
    r = client.post("/api/training-runs", json={"dataset_id": ds.id})
    assert r.status_code == 409
    detail = r.json()["detail"]
    assert str(first["id"]) in detail and "queued" in detail
    # the rejected start launched nothing
    assert ctx["started"] == before


def test_second_start_while_running_is_409(queue_env, in_memory_db):
    client, ctx = queue_env
    _seed_run(in_memory_db, ctx["users"][0], ctx["ds"], status="running")
    r = client.post("/api/training-runs", json={"dataset_id": ctx["ds"].id})
    assert r.status_code == 409
    assert "running" in r.json()["detail"]


def test_terminal_runs_do_not_block(queue_env, in_memory_db):
    client, ctx = queue_env
    _seed_run(in_memory_db, ctx["users"][0], ctx["ds"], status="completed")
    _seed_run(in_memory_db, ctx["users"][0], ctx["ds"], status="failed")
    r = client.post("/api/training-runs", json={"dataset_id": ctx["ds"].id})
    assert r.status_code == 201


def test_serialization_is_per_user(queue_env, in_memory_db):
    client, ctx = queue_env
    a, b = ctx["users"]
    _seed_run(in_memory_db, a, ctx["ds"], status="running")
    # B trains on B's own dataset (A's dataset 404s for B — owner scoping).
    ds_b = Dataset(user_id=b.id, name="s59-ds-b", description="d", source="manual")
    in_memory_db.add(ds_b)
    in_memory_db.commit()
    in_memory_db.refresh(ds_b)
    in_memory_db.add(QAPair(dataset_id=ds_b.id, question="q", answer="a"))
    in_memory_db.commit()
    ctx["as"](b)
    # B has no active run of their own, so B's start is accepted despite A's.
    r = client.post("/api/training-runs", json={"dataset_id": ds_b.id})
    assert r.status_code == 201
    body = r.json()
    assert body["queue_position"] == 2  # behind A's running row in the FIFO
    ctx["as"](a)
    assert client.post("/api/training-runs", json={"dataset_id": ctx["ds"].id}).status_code == 409


def test_queue_position_on_list_and_detail(queue_env, in_memory_db):
    client, ctx = queue_env
    a, b = ctx["users"]
    a_q = _seed_run(in_memory_db, a, ctx["ds"])                 # rank 1
    b_q = _seed_run(in_memory_db, b, ctx["ds"])                 # rank 2
    done = _seed_run(in_memory_db, a, ctx["ds"], status="completed")  # no rank
    ctx["as"](b)
    rows = {r["id"]: r for r in client.get("/api/training-runs").json()}
    assert a_q.id not in rows  # the list is owner-scoped: A's queued row is not B's
    assert rows[b_q.id]["queue_position"] == 2
    detail = client.get(f"/api/training-runs/{b_q.id}").json()
    assert detail["queue_position"] == 2
    terminal = client.get(f"/api/training-runs/{done.id}")  # other user's row: 404-no-leak
    assert terminal.status_code == 404


def test_running_row_has_no_queue_position(queue_env, in_memory_db):
    client, ctx = queue_env
    run = _seed_run(in_memory_db, ctx["users"][0], ctx["ds"], status="running")
    body = client.get(f"/api/training-runs/{run.id}").json()
    assert body["queue_position"] is None


def test_history_payload_unchanged(queue_env, in_memory_db):
    # S35's history shape is not a TrainingRunOut; the new field must not
    # leak into (or break) it.
    client, ctx = queue_env
    _seed_run(in_memory_db, ctx["users"][0], ctx["ds"], status="completed")
    rows = client.get("/api/training-runs/history").json()
    assert len(rows) == 1
    assert "queue_position" not in rows[0]
    assert rows[0]["status"] == "completed"
