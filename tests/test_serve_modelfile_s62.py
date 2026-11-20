"""S62 regressions: Model serving 1 — Ollama Modelfile generation + import smoke.

Three seams, all hermetic (no Ollama on the VPS — that's exactly what the
offline smoke is for; the real `ollama create` ride is Mac-verified, S70):

- training/modelfile.py pure helpers: tag slugify, GGUF discovery (f16
  preference per RESEARCH_MLX §4), Modelfile rendering, and the offline
  import validator mirroring ollama's parser;
- GET /api/fine-tuned-models/{id}/modelfile: owner-only even for public
  rows (the payload carries a device-local path — S26 — so strangers 404
  either way), quantize whitelist 400, honest has_gguf=false + conversion
  hint when the fused dir holds only safetensors, no owner metadata in the
  payload;
- cli/llmtuner/serve.py: dry run writes a Modelfile that passes its own
  smoke; --create fakes the `ollama` subprocess and asserts the exact argv
  plus the `ollama list` confirmation.
"""

import importlib.util
import json
import subprocess as real_subprocess
import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.security import get_current_user
from database import get_db
from models.fine_tuned_model import FineTunedModel
from models.user import User
from routers import fine_tuned_model as ftm_module
from training.modelfile import (
    build_modelfile,
    find_gguf,
    ollama_tag,
    validate_modelfile,
)

ROOT = Path(__file__).resolve().parent.parent

# ---- helpers -------------------------------------------------------------


def test_tag_slugify():
    assert ollama_tag("Finance Q&A ft-12") == "ft-finance-q-a-ft-12"
    assert ollama_tag("Llama-3.2-1B-Instruct-4bit-ft-7") == "ft-llama-3.2-1b-instruct-4bit-ft-7"
    assert ollama_tag("ft-already") == "ft-already"  # never double-prefix
    assert ollama_tag("___") == "ft-model"  # nothing survives the slug
    assert ollama_tag("Café Ünïcode 3B") == "ft-cafe-unicode-3b"  # accents transliterate, not vaporize


def test_find_gguf(tmp_path):
    # the file itself
    solo = tmp_path / "model.gguf"
    solo.write_bytes(b"GGUF")
    assert find_gguf(solo) == solo
    assert find_gguf(tmp_path / "not-here.gguf") is None
    assert find_gguf(tmp_path / "plain-file.txt" ) is None
    # a fused dir with one
    d = tmp_path / "fused_model"
    d.mkdir()
    (d / "ggml-model-f16.gguf").write_bytes(b"x")
    (d / "model-quantized.gguf").write_bytes(b"x")
    assert find_gguf(d) == d / "ggml-model-f16.gguf"  # f16 preferred (§4)
    (d / "ggml-model-f16.gguf").unlink()
    assert find_gguf(d) == d / "model-quantized.gguf"  # else sorted first
    # safetensors-only (today's real export output)
    empty = tmp_path / "mlx-only"
    empty.mkdir()
    (empty / "model.safetensors").write_bytes(b"x")
    assert find_gguf(empty) is None


def test_build_modelfile(tmp_path):
    gguf = tmp_path / "model-f16.gguf"
    gguf.write_bytes(b"x")
    text = build_modelfile(gguf)
    assert text.startswith(f"FROM {gguf}\n")
    assert text.endswith("\n")
    assert "QUANTIZE" not in text and "NOTES" not in text
    text = build_modelfile(gguf, quantize="q4_k_m", notes="made by  llmtuner\n  serve")
    lines = text.rstrip("\n").splitlines()
    assert lines == [f"FROM {gguf}", "QUANTIZE Q4_K_M", "NOTES made by llmtuner serve"]
    assert validate_modelfile(text, base_dir=tmp_path) == []


def test_validate_modelfile(tmp_path):
    good = tmp_path / "model.gguf"
    good.write_bytes(b"x")
    assert validate_modelfile(f"FROM {good}\n", base_dir=tmp_path) == []
    # relative FROM resolves against base_dir
    (tmp_path / "Modelfile").write_text(f"FROM ./{'model.gguf'}\n")
    assert validate_modelfile("FROM ./model.gguf\n", base_dir=tmp_path) == []
    # missing FROM
    errs = validate_modelfile("NOTES hi\n")
    assert any("no FROM" in e for e in errs)
    # unknown directive is rejected up-front, like ollama would
    errs = validate_modelfile("FROM ./model.gguf\nFROBNICATE yes\n", base_dir=tmp_path)
    assert any("unknown directive" in e for e in errs)
    # FROM pointing at nothing
    errs = validate_modelfile("FROM ./nope.gguf\n", base_dir=tmp_path)
    assert any("does not exist" in e for e in errs)
    # second FROM
    errs = validate_modelfile(f"FROM {good}\nFROM {good}\n")
    assert any("second FROM" in e for e in errs)
    # unknown quantize type
    errs = validate_modelfile(f"FROM {good}\nQUANTIZE Q99_X\n")
    assert any("not a known type" in e for e in errs)
    # no base_dir: existence is not checked (hosted box never has the bytes)
    assert validate_modelfile("FROM /Users/carlos/whatever.gguf\n") == []


# ---- endpoint -------------------------------------------------------------


@pytest.fixture()
def two_users(in_memory_db):
    owner = User(email="s62-owner@mail.lmt-pytest.dev", hashed_password="x", display_name="Owner O")
    other = User(email="s62-other@mail.lmt-pytest.dev", hashed_password="x")
    in_memory_db.add_all([owner, other])
    in_memory_db.commit()
    in_memory_db.refresh(owner)
    in_memory_db.refresh(other)
    return owner, other


@pytest.fixture()
def app_for(in_memory_db, two_users):
    owner, other = two_users
    state = {"user": owner}
    app = FastAPI()
    app.include_router(ftm_module.router)
    app.dependency_overrides[get_db] = lambda: in_memory_db
    app.dependency_overrides[get_current_user] = lambda: state["user"]
    with TestClient(app) as test_client:
        yield test_client, {"as": lambda u: state.update(user=u)}


def _model(in_memory_db, user, name="s62 model!", gguf_path=None, visibility="private", run_id=None):
    ft = FineTunedModel(
        user_id=user.id,
        training_run_id=run_id or 11,
        name=name,
        base_model="mlx-community/Llama-3.2-1B-Instruct-4bit",
        gguf_path=gguf_path,
        status="ready",
        visibility=visibility,
    )
    in_memory_db.add(ft)
    in_memory_db.commit()
    in_memory_db.refresh(ft)
    return ft


def test_modelfile_endpoint_owner_roundtrip(app_for, two_users, in_memory_db, tmp_path):
    client, _ = app_for
    owner, _ = two_users
    fused = tmp_path / "fused_model"
    fused.mkdir()
    (fused / "model-f16.gguf").write_bytes(b"x")
    ft = _model(in_memory_db, owner, name="Finance QA ft-11", gguf_path=str(fused))

    resp = client.get(f"/api/fine-tuned-models/{ft.id}/modelfile")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["ollama_tag"] == "ft-finance-qa-ft-11"
    assert body["has_gguf"] is True
    assert body["modelfile"].startswith(f"FROM {fused / 'model-f16.gguf'}")
    assert "QUANTIZE" not in body["modelfile"]
    assert body["create_command"] == f"ollama create ft-finance-qa-ft-11 -f Modelfile"
    assert body["hint"] is None
    # offline smoke agrees with the offline smoke in build_modelfile
    assert validate_modelfile(body["modelfile"]) == []


def test_modelfile_endpoint_quantize(app_for, two_users, in_memory_db, tmp_path):
    client, _ = app_for
    owner, _ = two_users
    (tmp_path / "m.gguf").write_bytes(b"x")
    ft = _model(in_memory_db, owner, gguf_path=str(tmp_path))
    resp = client.get(f"/api/fine-tuned-models/{ft.id}/modelfile?quantize=q4_k_m")
    assert resp.status_code == 200
    assert "QUANTIZE Q4_K_M" in resp.json()["modelfile"]
    bad = client.get(f"/api/fine-tuned-models/{ft.id}/modelfile?quantize=q99")
    assert bad.status_code == 400
    assert "Q4_K_M" in bad.json()["detail"]  # names the accepted types


def test_modelfile_endpoint_owner_only_even_public(app_for, two_users, in_memory_db, tmp_path):
    client, switch = app_for
    owner, other = two_users
    fused = tmp_path / "fused_model"
    fused.mkdir()
    (fused / "model.gguf").write_bytes(b"x")
    public_ft = _model(in_memory_db, owner, name="s62 pub!", gguf_path=str(fused),
                       visibility="public", run_id=41)
    private_ft = _model(in_memory_db, owner, name="s62 priv!", gguf_path=str(fused),
                        visibility="private", run_id=42)

    # device-local path rides the payload, so this endpoint is NOT the
    # library door: even a public row 404s for strangers (S31 wording).
    switch["as"](other)
    for ft in (public_ft, private_ft):
        resp = client.get(f"/api/fine-tuned-models/{ft.id}/modelfile")
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Fine-tuned model not found"
        assert "fused_model" not in resp.text  # no leak of the path in errors
    # unknown id: same door, same wording
    assert client.get("/api/fine-tuned-models/9999/modelfile").status_code == 404
    # and the owner still reads their own public row
    switch["as"](owner)
    assert client.get(f"/api/fine-tuned-models/{public_ft.id}/modelfile").status_code == 200


def test_modelfile_endpoint_no_gguf_is_honest(app_for, two_users, in_memory_db, tmp_path):
    client, _ = app_for
    owner, _ = two_users
    mlx_dir = tmp_path / "fused_model"
    mlx_dir.mkdir()
    (mlx_dir / "model.safetensors").write_bytes(b"x")
    ft = _model(in_memory_db, owner, gguf_path=str(mlx_dir))
    resp = client.get(f"/api/fine-tuned-models/{ft.id}/modelfile")
    assert resp.status_code == 200
    body = resp.json()
    assert body["has_gguf"] is False
    assert body["modelfile"] is None and body["create_command"] is None
    assert "convert_hf_to_gguf.py" in body["hint"]
    # never an owner-trapping half-file: the payload carries no account fields
    assert "email" not in json.dumps(body)


def test_modelfile_endpoint_fallback_source(app_for, two_users, in_memory_db):
    client, _ = app_for
    owner, _ = two_users
    # a run id no checkout will have on disk — the fallback path must not
    # silently prettify into a real dir
    ft = _model(in_memory_db, owner, gguf_path=None, run_id=9876543)
    resp = client.get(f"/api/fine-tuned-models/{ft.id}/modelfile")
    assert resp.status_code == 200
    body = resp.json()
    # chat.py's fallback shape for a row without a recorded path
    assert body["source"] == "_training_runs/9876543/fused_model"
    assert body["has_gguf"] is False  # that dir does not exist here, honest answer


# ---- CLI ---------------------------------------------------------------


def _load_serve():
    spec = importlib.util.spec_from_file_location(
        "llmtuner_serve_s62", ROOT / "cli" / "llmtuner" / "serve.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


serve_mod = _load_serve()


class FakeOllama:
    """Records every subprocess.run call; scripts rc + stdout per argv[1]."""

    def __init__(self, create_rc=0, list_output="MODEL SIZE\nft-finance-qa-ft-11 1.3GB\n"):
        self.calls = []
        self.create_rc = create_rc
        self.list_output = list_output

    def run(self, argv, **kwargs):
        self.calls.append((list(argv), kwargs))
        completed = real_subprocess.CompletedProcess(argv, 0, "", "")
        if argv[1] == "create":
            completed.returncode = self.create_rc
            if self.create_rc:
                completed.stderr = "Error: open gguf: no such file"
        elif argv[1] == "list":
            completed.stdout = self.list_output
        return completed


def test_cli_serve_dry_run(tmp_path, capsys, monkeypatch):
    fused = tmp_path / "fused_model"
    fused.mkdir()
    gguf = fused / "model-f16.gguf"
    gguf.write_bytes(b"x")
    fake = FakeOllama()
    monkeypatch.setattr(serve_mod, "subprocess", fake)
    monkeypatch.setattr(serve_mod, "_ollama_available", lambda: False)

    rc = serve_mod.serve_command(path=str(fused), name="Finance QA ft-11")
    assert rc == 0, capsys.readouterr().out
    assert fake.calls == []  # dry run never touches ollama
    text = (fused / "Modelfile").read_text()
    assert text.startswith(f"FROM {gguf}")
    assert "ft-finance-qa-ft-11" in capsys.readouterr().out  # next-step line
    assert validate_modelfile(text, base_dir=fused) == []


def test_cli_serve_no_gguf(tmp_path, capsys, monkeypatch):
    mlx = tmp_path / "fused_model"
    mlx.mkdir()
    monkeypatch.setattr(serve_mod, "_ollama_available", lambda: True)
    rc = serve_mod.serve_command(path=str(mlx))
    out = capsys.readouterr().out
    assert rc == 1 and "convert_hf_to_gguf.py" in out
    assert not (mlx / "Modelfile").exists()  # never write a half-broken file


def test_cli_serve_create_success(tmp_path, capsys, monkeypatch):
    gguf = tmp_path / "model-f16.gguf"
    gguf.write_bytes(b"x")
    fake = FakeOllama()
    monkeypatch.setattr(serve_mod, "subprocess", fake)
    monkeypatch.setattr(serve_mod, "_ollama_available", lambda: True)

    rc = serve_mod.serve_command(path=str(gguf), name="Finance QA ft-11", create=True)
    assert rc == 0, capsys.readouterr().out
    assert "live in `ollama list`" in capsys.readouterr().out
    create_call, list_call = fake.calls
    assert create_call[0] == ["ollama", "create", "ft-finance-qa-ft-11",
                              "-f", str(tmp_path / "Modelfile")]
    assert list_call[0] == ["ollama", "list"]


def test_cli_serve_create_reports_missing_tag(tmp_path, capsys, monkeypatch):
    gguf = tmp_path / "model.gguf"
    gguf.write_bytes(b"x")
    fake = FakeOllama(list_output="MODEL SIZE\nllama3.2:1b 1.3GB\n")
    monkeypatch.setattr(serve_mod, "subprocess", fake)
    monkeypatch.setattr(serve_mod, "_ollama_available", lambda: True)
    rc = serve_mod.serve_command(path=str(gguf), name="x", create=True)
    out = capsys.readouterr().out
    assert rc == 1 and "not in `ollama list`" in out


def test_cli_serve_create_failure_tail(tmp_path, capsys, monkeypatch):
    gguf = tmp_path / "model.gguf"
    gguf.write_bytes(b"x")
    fake = FakeOllama(create_rc=1)
    monkeypatch.setattr(serve_mod, "subprocess", fake)
    monkeypatch.setattr(serve_mod, "_ollama_available", lambda: True)
    rc = serve_mod.serve_command(path=str(gguf), name="x", create=True)
    out = capsys.readouterr().out
    assert rc == 1 and "exited 1" in out and "no such file" in out
    assert len(fake.calls) == 1  # never asked `ollama list` after a failed create


def test_cli_serve_run_id_and_latest(tmp_path, monkeypatch):
    root = tmp_path / "_training_runs"
    for run in (3, 7):
        d = root / str(run) / "fused_model"
        d.mkdir(parents=True)
        (d / "model-f16.gguf").write_bytes(b"x")
    monkeypatch.setattr(serve_mod, "TRAINING_ROOT", root)
    monkeypatch.setattr(serve_mod, "_ollama_available", lambda: False)
    monkeypatch.setattr(serve_mod, "subprocess", FakeOllama())

    assert serve_mod.serve_command(run_id=3) == 0
    assert (root / "3" / "fused_model" / "Modelfile").exists()
    assert serve_mod.serve_command(run_id=99) == 1
    assert serve_mod.serve_command(latest=True) == 0
    assert (root / "7" / "fused_model" / "Modelfile").exists()  # highest id wins


def test_cli_serve_quiet_errors(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(serve_mod, "_ollama_available", lambda: False)
    assert serve_mod.serve_command(path=str(tmp_path / "nowhere")) == 1
    assert "No such file" in capsys.readouterr().out
    assert serve_mod.serve_command() == 1  # no flags at all
    assert "Nothing to serve" in capsys.readouterr().out
