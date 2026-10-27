"""S35 (#36) regressions: run history 1 — the /api/training-runs/history list.

Guarantees covered:
- one row per run with dataset name, base model, iters and final loss;
- final loss is the LAST step parsed from the run's train.log (order-tolerant),
  and None when the run has no log/points yet (queued/running);
- owner-scoped (another user's runs never appear — no existence leak);
- runs whose dataset was deleted fall back to "(deleted dataset)";
- GET /history matches before /{run_id} (route order) and the int route still
  resolves for real ids.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.security import get_current_user
from database import get_db
from models.dataset import Dataset
from models.training_run import TrainingRun
from models.user import User
from routers import training_run as training_run_module
from training import runner as runner_module


@pytest.fixture()
def hist_env(in_memory_db, two_users_s35, tmp_path, monkeypatch):
    # Redirect the per-run workspaces into a temp dir so train.log fixtures
    # never touch the repo's _training_runs/.
    monkeypatch.setattr(runner_module, "TRAINING_ROOT", tmp_path)

    owner, other = two_users_s35
    state = {"user": owner}

    app = FastAPI()
    app.include_router(training_run_module.router)
    app.dependency_overrides[get_db] = lambda: in_memory_db
    app.dependency_overrides[get_current_user] = lambda: state["user"]

    with TestClient(app) as test_client:
        yield test_client, {"owner": owner, "other": other, "as": lambda u: state.update(user=u)}


@pytest.fixture()
def two_users_s35(in_memory_db):
    owner = User(email="s35-owner@mail.lmt-pytest.dev", hashed_password="x", display_name="Hist H")
    other = User(email="s35-other@mail.lmt-pytest.dev", hashed_password="x")
    in_memory_db.add_all([owner, other])
    in_memory_db.commit()
    in_memory_db.refresh(owner)
    in_memory_db.refresh(other)
    return owner, other


def _dataset(db, user, name="hist-src"):
    ds = Dataset(user_id=user.id, name=name, description="d", source="manual")
    db.add(ds)
    db.commit()
    db.refresh(ds)
    return ds


def _run(db, user, dataset, **kw):
    run = TrainingRun(
        user_id=user.id,
        dataset_id=dataset.id,
        base_model=kw.pop("base_model", "mlx-community/Llama-3.2-1B-Instruct-4bit"),
        method=kw.pop("method", "qlora"),
        iters=kw.pop("iters", 100),
        status=kw.pop("status", "completed"),
        **kw,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def _write_log(tmp_path, run_id, text):
    d = tmp_path / str(run_id)
    d.mkdir(parents=True, exist_ok=True)
    (d / "train.log").write_text(text, encoding="utf-8")


def test_history_row_shape_and_final_loss(hist_env, in_memory_db, tmp_path):
    client, ctx = hist_env
    ds = _dataset(in_memory_db, ctx["owner"])
    run = _run(in_memory_db, ctx["owner"], ds, iters=200)
    _write_log(
        tmp_path, run.id,
        "Iter 100: Train loss 2.10000, Validation loss 0.00000\n"
        "Iter 200: Train loss 1.40000, Validation loss 0.00000\n",
    )

    rows = client.get("/api/training-runs/history").json()
    assert len(rows) == 1
    row = rows[0]
    assert row["id"] == run.id
    assert row["dataset_name"] == "hist-src"
    assert row["base_model"] == "mlx-community/Llama-3.2-1B-Instruct-4bit"
    assert row["method"] == "qlora"
    assert row["iters"] == 200
    assert row["status"] == "completed"
    assert row["final_loss"] == 1.4


def test_final_loss_uses_last_step_not_last_line(hist_env, in_memory_db, tmp_path):
    # tqdm rewrites can land the older step last in the file; the parser sorts
    # by step, and the history row must carry the highest-step loss.
    client, ctx = hist_env
    ds = _dataset(in_memory_db, ctx["owner"])
    run = _run(in_memory_db, ctx["owner"], ds)
    _write_log(
        tmp_path, run.id,
        "Iter 200: Train loss 1.35000\nIter 100: Train loss 2.20000\n",
    )
    rows = client.get("/api/training-runs/history").json()
    assert rows[0]["final_loss"] == 1.35


def test_history_none_final_loss_without_log(hist_env, in_memory_db):
    client, ctx = hist_env
    ds = _dataset(in_memory_db, ctx["owner"])
    _run(in_memory_db, ctx["owner"], ds, status="queued")
    rows = client.get("/api/training-runs/history").json()
    assert len(rows) == 1
    assert rows[0]["final_loss"] is None


def test_history_owner_scoped(hist_env, in_memory_db):
    client, ctx = hist_env
    ds = _dataset(in_memory_db, ctx["owner"])
    _run(in_memory_db, ctx["owner"], ds)
    assert len(client.get("/api/training-runs/history").json()) == 1

    ctx["as"](ctx["other"])
    assert client.get("/api/training-runs/history").json() == []


def test_history_deleted_dataset_fallback(hist_env, in_memory_db):
    client, ctx = hist_env
    ds = _dataset(in_memory_db, ctx["owner"])
    _run(in_memory_db, ctx["owner"], ds)
    in_memory_db.delete(ds)
    in_memory_db.commit()
    rows = client.get("/api/training-runs/history").json()
    assert rows[0]["dataset_name"] == "(deleted dataset)"
    assert rows[0]["dataset_id"] == ds.id


def test_history_newest_first(hist_env, in_memory_db):
    client, ctx = hist_env
    ds = _dataset(in_memory_db, ctx["owner"])
    older = _run(in_memory_db, ctx["owner"], ds)
    newer = _run(in_memory_db, ctx["owner"], ds, base_model="mlx-community/Qwen2.5-1.5B-Instruct-4bit")
    rows = client.get("/api/training-runs/history").json()
    assert [r["id"] for r in rows] == [newer.id, older.id]


def test_history_route_does_not_shadow_run_id(hist_env, in_memory_db):
    client, ctx = hist_env
    ds = _dataset(in_memory_db, ctx["owner"])
    run = _run(in_memory_db, ctx["owner"], ds)
    # /history returns the list (200), and /{run_id} still resolves ints.
    assert client.get("/api/training-runs/history").status_code == 200
    detail = client.get(f"/api/training-runs/{run.id}")
    assert detail.status_code == 200
    assert detail.json()["id"] == run.id
