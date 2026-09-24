"""Settings/env-precedence tests for S9 (issue #12).

Precedence order under pydantic-settings (this is what install.sh relies on):
real process env > ~/.llmtuner/.env > backend/.env > field defaults.
Each Settings() here is built with an explicit _env_file so the developer's or
the CI machine's real .env files can never leak in or get clobbered.
"""

from config import Settings, llmtuner_home


def _write(tmp_path, name, **kv):
    p = tmp_path / name
    p.write_text("\n".join(f"{k}={v}" for k, v in kv.items()), encoding="utf-8")
    return str(p)


def test_os_env_beats_dotenv_file(tmp_path, monkeypatch):
    env_file = _write(tmp_path, "app.env", JWT_SECRET_KEY="from-dotenv")
    monkeypatch.setenv("JWT_SECRET_KEY", "from-os-env")
    assert Settings(_env_file=env_file).jwt_secret_key == "from-os-env"


def test_installer_file_later_in_tuple_wins(tmp_path, monkeypatch):
    monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
    checkout = _write(tmp_path, "backend.env", JWT_SECRET_KEY="from-checkout")
    installer = _write(tmp_path, "home.env", JWT_SECRET_KEY="from-installer")
    # config.Settings.model_config lists backend/.env first and ~/.llmtuner/.env
    # second; the tuple order is what makes the installer file authoritative.
    s = Settings(_env_file=(checkout, installer))
    assert s.jwt_secret_key == "from-installer"
    s_flip = Settings(_env_file=(installer, checkout))
    assert s_flip.jwt_secret_key == "from-checkout"


def test_defaults_when_nothing_configured(monkeypatch):
    for var in ("JWT_SECRET_KEY", "ACCESS_TOKEN_EXPIRE_MINUTES", "OLLAMA_BASE_URL"):
        monkeypatch.delenv(var, raising=False)
    s = Settings(_env_file=None)
    assert s.jwt_algorithm == "HS256"
    assert s.access_token_expire_minutes == 60
    assert s.ollama_base_url == "http://localhost:11434"
    assert s.local_mode is False


def test_llmtuner_home_env_var_and_fallback(monkeypatch, tmp_path):
    from pathlib import Path

    target = tmp_path / "home-dir"
    monkeypatch.setenv("LLMTUNER_HOME", str(target))
    assert llmtuner_home() == target
    assert target.is_dir()  # created on demand
    monkeypatch.delenv("LLMTUNER_HOME")
    assert llmtuner_home() == Path.home() / ".llmtuner"


def test_resolved_database_url(tmp_path, monkeypatch):
    for var in ("DATABASE_URL", "LLMTUNER_HOME"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("LLMTUNER_HOME", str(tmp_path))
    s = Settings(_env_file=None)
    assert s.resolved_database_url() == f"sqlite:///{tmp_path / 'app.db'}"
    hosted = Settings(_env_file=None, database_url="postgresql://db/app")
    assert hosted.resolved_database_url() == "postgresql://db/app"


def test_service_tokens_and_api_keys_are_plain_strings(tmp_path, monkeypatch):
    """S8 shape: API_SERVICE_TOKENS is parsed by core.security, not by Settings."""
    for var in ("API_SERVICE_TOKENS", "ANTHROPIC_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    env_file = _write(tmp_path, "s.env", API_SERVICE_TOKENS="a:1,b:2")
    s = Settings(_env_file=env_file)
    assert s.api_service_tokens == "a:1,b:2"
    assert s.anthropic_api_key is None
