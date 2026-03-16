"""Application configuration for FeedPilot.

Uses pydantic-settings for type-safe environment variable
loading with explicit ConfigDict per Pydantic V2 standard.
"""

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    app_name: str = "FeedPilot API"
    app_version: str = "0.1.0"
    debug: bool = False
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    database_url: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings.

    Uses lru_cache so settings are only loaded once
    per process — not on every request.

    Returns:
        Validated Settings instance.
    """
    return Settings()