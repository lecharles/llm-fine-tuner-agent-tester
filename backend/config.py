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

    def resolved_database_url(self) -> str:
        return self.database_url or f"sqlite:///{llmtuner_home() / 'app.db'}"

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()
