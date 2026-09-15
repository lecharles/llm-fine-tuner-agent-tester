import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


def llmtuner_home() -> Path:
    """Local app data directory. Everything a solo user needs lives here."""
    home = Path(os.getenv("LLMTUNER_HOME", Path.home() / ".llmtuner"))
    home.mkdir(parents=True, exist_ok=True)
    return home


class Settings(BaseSettings):
    # Phase 6 slice 2: zero-infra default. SQLite in the app home unless a
    # hosted DATABASE_URL (Postgres) is provided explicitly.
    database_url: str = ""
    jwt_secret_key: str = "llmtuner-local-dev-secret"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None
    static_dir: str | None = None  # optional path to the built frontend (Phase 6 slice 1)
    local_mode: bool = False  # Phase 6 slice 3: single-user local bootstrap

    # Phase 6 slice 6: local generation fallback. When both hosted providers are
    # exhausted (out of credit) or unconfigured, generation can fall through to
    # Ollama on this machine, which is free. Auto-discovers installed models.
    ollama_base_url: str = "http://localhost:11434"
    generation_local_models: str = ""  # comma list; empty = use all installed

    def resolved_database_url(self) -> str:
        return self.database_url or f"sqlite:///{llmtuner_home() / 'app.db'}"

    model_config = SettingsConfigDict(
        # Load keys from both places, absolute paths only:
        # - backend/.env: developer checkout convention
        # - ~/.llmtuner/.env: where install.sh saves API keys
        # Later entries win, so the installer file is authoritative.
        env_file=(Path(__file__).resolve().parent / ".env", llmtuner_home() / ".env"),
    )


settings = Settings()
