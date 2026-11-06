"""Runtime settings, read from environment variables or a local .env file."""

from functools import cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://hpc:hpc@localhost:5432/hpc_rag"
    chat_model: str = "anthropic:claude-sonnet-5-5"
    # Unset: the provider default. Claude Sonnet 5.5 and newer reject any other
    # value; set it only for models that accept it (e.g. vLLM in deployment).
    temperature: float | None = None
    anthropic_api_key: str | None = None
    cors_origins: list[str] = []


@cache
def get_settings() -> Settings:
    return Settings()
