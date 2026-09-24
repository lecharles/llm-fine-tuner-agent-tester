"""Splash + SPA mount tests for S9 (issue #12).

static_serve.py has two user-visible contracts:
- no UI build  -> GET / renders the status splash with every @@token@@ filled;
- built dist   -> deep links fall back to index.html while /api/* stays JSON.
"""

import pytest

from fastapi import FastAPI
from fastapi.testclient import TestClient

import static_serve


@pytest.fixture()
def blank_settings(monkeypatch):
    """Pin the knobs render_splash reads so output is deterministic."""
    import config

    monkeypatch.setattr(config.settings, "local_mode", False)
    monkeypatch.setattr(config.settings, "anthropic_api_key", None)
    monkeypatch.setattr(config.settings, "openai_api_key", None)


def test_render_splash_fills_every_token(blank_settings):
    html = static_serve.render_splash()
    assert "@@" not in html, "unfilled token left in splash"
    assert "LLM Tuner server is up" in html
    # key badges reflect config, red when unset
    assert html.count('<span class="bad">not set</span>') == 2
    assert '<span class="bad">off</span>' in html  # local mode off


def test_render_splash_shows_configured_state(monkeypatch, tmp_path):
    import config

    monkeypatch.setattr(config.settings, "local_mode", True)
    monkeypatch.setattr(config.settings, "anthropic_api_key", "sk-ant-fake")
    monkeypatch.setattr(config.settings, "openai_api_key", "sk-fake")
    monkeypatch.setattr(config.settings, "static_dir", str(tmp_path))
    html = static_serve.render_splash()
    assert "@@" not in html
    assert '<span class="ok">on</span>' in html
    assert html.count('<span class="ok">set</span>') == 2
    assert str(tmp_path) in html  # expected-dist row
    # The rendered page must never leak key material, only set/not-set badges.
    assert "sk-ant-fake" not in html and "sk-fake" not in html


def test_mount_spa_without_build_serves_splash(monkeypatch, tmp_path):
    import config

    monkeypatch.setattr(config.settings, "static_dir", str(tmp_path / "no-dist"))
    app = FastAPI()
    assert static_serve.mount_spa(app) is False
    r = TestClient(app).get("/")
    assert r.status_code == 200
    assert "server up" in r.text.lower()


def _fake_dist(tmp_path):
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>SPA</title>", encoding="utf-8")
    (dist / "assets" / "app.js").write_text("console.log(1)", encoding="utf-8")
    return dist


def test_mount_spa_with_build_routes_correctly(monkeypatch, tmp_path):
    import config

    dist = _fake_dist(tmp_path)
    monkeypatch.setattr(config.settings, "static_dir", str(dist))
    app = FastAPI()
    assert static_serve.mount_spa(app) is True
    c = TestClient(app)
    assert c.get("/").text == "<!doctype html><title>SPA</title>"
    assert c.get("/train").text == "<!doctype html><title>SPA</title>"  # deep link
    assert c.get("/assets/app.js").status_code == 200
    api = c.get("/api/nope")
    assert api.status_code == 404 and api.json()["detail"] == "Not Found"


def test_path_traversal_cannot_escape_dist(monkeypatch, tmp_path):
    import config

    dist = _fake_dist(tmp_path)
    (tmp_path / "secret.env").write_text("SECRET_API_KEY=never-serve-me", encoding="utf-8")
    monkeypatch.setattr(config.settings, "static_dir", str(dist))
    app = FastAPI()
    static_serve.mount_spa(app)
    c = TestClient(app)
    # Raw ".." is normalized away by the client; the encoded form reaches the
    # route as "../secret.env" and must still be refused by the is_relative_to
    # guard (the SPA fallback answers instead of the file).
    r = c.get("/%2e%2e/secret.env")
    assert "never-serve-me" not in r.text
    assert r.text == "<!doctype html><title>SPA</title>"
