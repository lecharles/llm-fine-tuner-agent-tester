from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None
    static_dir: str | None = None  # optional path to the built frontend (Phase 6 slice 1)

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()